package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

// BridgeConfig holds configuration for invoking the Python Core Bridge.
type BridgeConfig struct {
	PythonBin  string
	PythonPath string
	DBPath     string
	Timeout    time.Duration
}

// DefaultBridgeConfig returns reasonable defaults for development and Pi runtime.
func DefaultBridgeConfig() *BridgeConfig {
	pyBin := "python3"
	if _, err := os.Stat("/usr/bin/python3"); err == nil {
		pyBin = "/usr/bin/python3"
	}

	pyPath := "src"
	if _, err := os.Stat("/home/mcp-gateway/mcp-gateway/src"); err == nil {
		pyPath = "/home/mcp-gateway/mcp-gateway/src"
	}

	return &BridgeConfig{
		PythonBin:  pyBin,
		PythonPath: pyPath,
		Timeout:    35 * time.Second,
	}
}

// CallBridge invokes python3 -m mcp_gateway.bridge invoke <tool> <argsJSON>.
func (b *BridgeConfig) CallBridge(ctx context.Context, toolName string, argsJSON []byte) ([]byte, bool, error) {
	if len(argsJSON) == 0 {
		argsJSON = []byte("{}")
	}

	ctx, cancel := context.WithTimeout(ctx, b.Timeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, b.PythonBin, "-m", "mcp_gateway.bridge", "invoke", toolName, string(argsJSON))
	
	// Inherit environment and prepend PYTHONPATH
	env := os.Environ()
	if b.PythonPath != "" {
		absPath, err := filepath.Abs(b.PythonPath)
		if err == nil {
			env = append(env, fmt.Sprintf("PYTHONPATH=%s", absPath))
		} else {
			env = append(env, fmt.Sprintf("PYTHONPATH=%s", b.PythonPath))
		}
	}
	if b.DBPath != "" {
		env = append(env, fmt.Sprintf("MCP_GATEWAY_DB=%s", b.DBPath))
	}
	cmd.Env = env

	var stdout, stderr bytes.Buffer
	cmd.Stdout = &stdout
	cmd.Stderr = &stderr

	err := cmd.Run()
	outBytes := stdout.Bytes()

	// Parse JSON to determine Core-level success
	var resp struct {
		OK    bool           `json:"ok"`
		Tool  string         `json:"tool"`
		Error map[string]any `json:"error"`
	}

	if jsonErr := json.Unmarshal(outBytes, &resp); jsonErr == nil {
		return outBytes, !resp.OK, nil
	}

	// If not JSON, it was a process error
	if err != nil {
		errResp, _ := json.Marshal(map[string]any{
			"ok":   false,
			"tool": toolName,
			"error": map[string]any{
				"code":    "BRIDGE_EXEC_ERROR",
				"message": fmt.Sprintf("Subprocess error: %v, stderr: %s", err, stderr.String()),
			},
		})
		return errResp, true, nil
	}

	return outBytes, false, nil
}

// NewGatewayServer creates an official MCP server registering the 8 Core tools.
func NewGatewayServer(bridge *BridgeConfig) *mcp.Server {
	server := mcp.NewServer(&mcp.Implementation{
		Name:    "mcp-gateway-adapter",
		Title:   "MCP Raspberry Pi Gateway Official Adapter",
		Version: "0.2.0",
	}, nil)

	handlerFor := func(toolName string) mcp.ToolHandler {
		return func(ctx context.Context, req *mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			rawArgs := req.Params.Arguments
			outBytes, isErr, err := bridge.CallBridge(ctx, toolName, rawArgs)
			if err != nil {
				return nil, err
			}

			var structured map[string]any
			_ = json.Unmarshal(outBytes, &structured)

			return &mcp.CallToolResult{
				IsError: isErr,
				Content: []mcp.Content{
					&mcp.TextContent{Text: string(outBytes)},
				},
				StructuredContent: structured,
			}, nil
		}
	}

	// 1. health
	server.AddTool(&mcp.Tool{
		Name:        "health",
		Description: "Check gateway health, uptime, version, and target count",
		InputSchema: map[string]any{
			"type": "object",
		},
	}, handlerFor("health"))

	// 2. list_targets
	server.AddTool(&mcp.Tool{
		Name:        "list_targets",
		Description: "Return safe list of configured targets without secrets",
		InputSchema: map[string]any{
			"type": "object",
		},
	}, handlerFor("list_targets"))

	// 3. target_status
	server.AddTool(&mcp.Tool{
		Name:        "target_status",
		Description: "Verify reachability and latency of a target machine",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"target": map[string]any{
					"type":        "string",
					"description": "Configured Target ID (e.g. termux-main)",
				},
			},
			"required": []string{"target"},
		},
	}, handlerFor("target_status"))

	// 4. list_directory
	server.AddTool(&mcp.Tool{
		Name:        "list_directory",
		Description: "List directory contents under an authorized project",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"target": map[string]any{
					"type":        "string",
					"description": "Target ID",
				},
				"project": map[string]any{
					"type":        "string",
					"description": "Project ID",
				},
				"relative_path": map[string]any{
					"type":        "string",
					"description": "Relative path within project root (default: '.')",
				},
			},
			"required": []string{"target", "project"},
		},
	}, handlerFor("list_directory"))

	// 5. file_stat
	server.AddTool(&mcp.Tool{
		Name:        "file_stat",
		Description: "Get metadata of a file or directory within a project",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"target": map[string]any{
					"type":        "string",
					"description": "Target ID",
				},
				"project": map[string]any{
					"type":        "string",
					"description": "Project ID",
				},
				"relative_path": map[string]any{
					"type":        "string",
					"description": "Relative path to file or directory",
				},
			},
			"required": []string{"target", "project", "relative_path"},
		},
	}, handlerFor("file_stat"))

	// 6. read_file
	server.AddTool(&mcp.Tool{
		Name:        "read_file",
		Description: "Read text file content safely within project boundaries",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"target": map[string]any{
					"type":        "string",
					"description": "Target ID",
				},
				"project": map[string]any{
					"type":        "string",
					"description": "Project ID",
				},
				"relative_path": map[string]any{
					"type":        "string",
					"description": "Relative path to text file",
				},
			},
			"required": []string{"target", "project", "relative_path"},
		},
	}, handlerFor("read_file"))

	// 7. git_status
	server.AddTool(&mcp.Tool{
		Name:        "git_status",
		Description: "Run 'git status --short' on authorized project repository",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"target": map[string]any{
					"type":        "string",
					"description": "Target ID",
				},
				"project": map[string]any{
					"type":        "string",
					"description": "Project ID",
				},
			},
			"required": []string{"target", "project"},
		},
	}, handlerFor("git_status"))

	// 8. run_task
	server.AddTool(&mcp.Tool{
		Name:        "run_task",
		Description: "Execute an allowlisted pre-configured task",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"target": map[string]any{
					"type":        "string",
					"description": "Target ID",
				},
				"project": map[string]any{
					"type":        "string",
					"description": "Project ID",
				},
				"task": map[string]any{
					"type":        "string",
					"description": "Pre-configured task name in project allowlist",
				},
			},
			"required": []string{"target", "project", "task"},
		},
	}, handlerFor("run_task"))

	// 9. write_file
	server.AddTool(&mcp.Tool{
		Name:        "write_file",
		Description: "Safely write or mutate a text file in an authorized project with atomic replacement and hash verification",
		InputSchema: map[string]any{
			"type": "object",
			"properties": map[string]any{
				"target": map[string]any{
					"type":        "string",
					"description": "Target ID",
				},
				"project": map[string]any{
					"type":        "string",
					"description": "Project ID",
				},
				"relative_path": map[string]any{
					"type":        "string",
					"description": "Relative path to file within project root",
				},
				"content": map[string]any{
					"type":        "string",
					"description": "UTF-8 text content to write",
				},
				"expected_sha256": map[string]any{
					"type":        "string",
					"description": "Expected SHA256 of existing file before overwrite (required for overwrite unless create=true)",
				},
				"dry_run": map[string]any{
					"type":        "boolean",
					"description": "If true, returns diff and sha256 without mutating the target file",
				},
				"create": map[string]any{
					"type":        "boolean",
					"description": "If true, creates a new file (fails if file already exists)",
				},
			},
			"required": []string{"target", "project", "relative_path", "content"},
		},
	}, handlerFor("write_file"))

	return server
}

// RunStdio starts the MCP server over standard input/output.
func RunStdio(ctx context.Context, server *mcp.Server) error {
	return server.Run(ctx, &mcp.StdioTransport{})
}

// RunHTTP starts the Streamable HTTP server on the specified bind address.
func RunHTTP(ctx context.Context, server *mcp.Server, bindAddr string) error {
	handler := mcp.NewStreamableHTTPHandler(func(r *http.Request) *mcp.Server {
		return server
	}, &mcp.StreamableHTTPOptions{
		Stateless:                    true,
		PropagateRequestCancellation: true,
	})

	mux := http.NewServeMux()
	mux.Handle("/mcp", handler)
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"status":"ok","adapter":"mcp-gateway-adapter","version":"0.2.0"}`)
	})

	srv := &http.Server{
		Addr:         bindAddr,
		Handler:      mux,
		ReadTimeout:  60 * time.Second,
		WriteTimeout: 60 * time.Second,
	}

	go func() {
		<-ctx.Done()
		shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = srv.Shutdown(shutdownCtx)
	}()

	log.Printf("Starting MCP Streamable HTTP server on http://%s/mcp (stateless)", bindAddr)
	if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
		return err
	}
	return nil
}
