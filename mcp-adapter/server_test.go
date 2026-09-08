package main

import (
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"testing"
	"time"

	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func getTestBridgeConfig() *BridgeConfig {
	pyPath, _ := filepath.Abs("../src")
	return &BridgeConfig{
		PythonBin:  "python3",
		PythonPath: pyPath,
		Timeout:    10 * time.Second,
	}
}

func TestServerToolDiscovery(t *testing.T) {
	ctx := context.Background()
	bridge := getTestBridgeConfig()
	server := NewGatewayServer(bridge)

	tServer, tClient := mcp.NewInMemoryTransports()
	go func() {
		_ = server.Run(ctx, tServer)
	}()

	client := mcp.NewClient(&mcp.Implementation{
		Name:    "test-client",
		Version: "1.0.0",
	}, nil)

	session, err := client.Connect(ctx, tClient, nil)
	if err != nil {
		t.Fatalf("client.Connect failed: %v", err)
	}
	defer session.Close()

	// 1. List tools
	toolsList, err := session.ListTools(ctx, nil)
	if err != nil {
		t.Fatalf("ListTools failed: %v", err)
	}

	expectedTools := map[string]bool{
		"health":         false,
		"list_targets":   false,
		"target_status":  false,
		"list_directory": false,
		"file_stat":      false,
		"read_file":      false,
		"git_status":     false,
		"run_task":       false,
		"write_file":     false,
	}

	if len(toolsList.Tools) != len(expectedTools) {
		t.Errorf("Expected %d tools, got %d", len(expectedTools), len(toolsList.Tools))
	}

	for _, tool := range toolsList.Tools {
		if _, exists := expectedTools[tool.Name]; exists {
			expectedTools[tool.Name] = true
		} else {
			t.Errorf("Unexpected tool discovered: %s", tool.Name)
		}
	}

	for name, found := range expectedTools {
		if !found {
			t.Errorf("Expected tool %s was not found in discovery", name)
		}
	}
}

func TestServerHealthCall(t *testing.T) {
	ctx := context.Background()
	bridge := getTestBridgeConfig()
	server := NewGatewayServer(bridge)

	tServer, tClient := mcp.NewInMemoryTransports()
	go func() {
		_ = server.Run(ctx, tServer)
	}()

	client := mcp.NewClient(&mcp.Implementation{
		Name:    "test-client",
		Version: "1.0.0",
	}, nil)

	session, err := client.Connect(ctx, tClient, nil)
	if err != nil {
		t.Fatalf("client.Connect failed: %v", err)
	}
	defer session.Close()

	// Call health
	res, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name: "health",
	})
	if err != nil {
		t.Fatalf("session.CallTool health failed: %v", err)
	}

	if res.IsError {
		t.Fatalf("health returned isError=true: %+v", res)
	}

	if len(res.Content) == 0 {
		t.Fatalf("health returned no content")
	}

	textContent, ok := res.Content[0].(*mcp.TextContent)
	if !ok {
		t.Fatalf("expected TextContent, got %T", res.Content[0])
	}

	var jsonOut map[string]any
	if err := json.Unmarshal([]byte(textContent.Text), &jsonOut); err != nil {
		t.Fatalf("failed to parse JSON from health: %v", err)
	}

	if jsonOut["ok"] != true {
		t.Errorf("expected ok=true, got %v", jsonOut["ok"])
	}
}

func TestServerInvalidToolAndArgs(t *testing.T) {
	ctx := context.Background()
	bridge := getTestBridgeConfig()
	server := NewGatewayServer(bridge)

	tServer, tClient := mcp.NewInMemoryTransports()
	go func() {
		_ = server.Run(ctx, tServer)
	}()

	client := mcp.NewClient(&mcp.Implementation{
		Name:    "test-client",
		Version: "1.0.0",
	}, nil)

	session, err := client.Connect(ctx, tClient, nil)
	if err != nil {
		t.Fatalf("client.Connect failed: %v", err)
	}
	defer session.Close()

	// 1. Call non-existent tool -> SDK returns protocol error
	_, err = session.CallTool(ctx, &mcp.CallToolParams{
		Name: "non_existent_tool",
	})
	if err == nil {
		t.Errorf("expected error for non_existent_tool, got nil")
	}

	// 2. Call tool with missing arguments -> Core returns isError=true with INVALID_ARGUMENTS
	res, err := session.CallTool(ctx, &mcp.CallToolParams{
		Name: "target_status",
	})
	if err != nil {
		t.Fatalf("session.CallTool unexpected protocol err: %v", err)
	}
	if !res.IsError {
		t.Errorf("expected isError=true for target_status with missing args")
	}

	textContent := res.Content[0].(*mcp.TextContent)
	var jsonOut map[string]any
	_ = json.Unmarshal([]byte(textContent.Text), &jsonOut)
	errMap, ok := jsonOut["error"].(map[string]any)
	if !ok || errMap["code"] != "INVALID_ARGUMENTS" {
		t.Errorf("expected INVALID_ARGUMENTS error code, got: %v", jsonOut)
	}
}

func TestStreamableHTTPHandler(t *testing.T) {
	bridge := getTestBridgeConfig()
	server := NewGatewayServer(bridge)

	handler := mcp.NewStreamableHTTPHandler(func(r *http.Request) *mcp.Server {
		return server
	}, &mcp.StreamableHTTPOptions{
		Stateless: true,
	})

	mux := http.NewServeMux()
	mux.Handle("/mcp", handler)
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		fmt.Fprintf(w, `{"status":"ok","adapter":"mcp-gateway-adapter","version":"0.2.0"}`)
	})

	ts := httptest.NewServer(mux)
	defer ts.Close()

	// Test GET /health
	resp, err := http.Get(ts.URL + "/health")
	if err != nil {
		t.Fatalf("GET /health failed: %v", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusOK {
		t.Errorf("expected 200 OK, got %d", resp.StatusCode)
	}

	// Test Stateless MCP endpoint: GET /mcp returns 405 Method Not Allowed in stateless mode
	resp2, err := http.Get(ts.URL + "/mcp")
	if err != nil {
		t.Fatalf("GET /mcp failed: %v", err)
	}
	defer resp2.Body.Close()
	if resp2.StatusCode != http.StatusMethodNotAllowed {
		t.Errorf("expected 405 for GET /mcp in stateless mode, got %d", resp2.StatusCode)
	}
}
