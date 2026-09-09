package main

import (
	"context"
	"flag"
	"fmt"
	"log"
	"os"
	"os/signal"
	"syscall"
)

func main() {
	log.SetOutput(os.Stderr)
	var (
		transportFlag = flag.String("transport", "stdio", "Transport mode: stdio or http")
		bindFlag      = flag.String("bind", "127.0.0.1:8090", "Bind address for Streamable HTTP mode (default: 127.0.0.1:8090)")
		pythonFlag    = flag.String("python", "", "Path to python3 binary")
		pythonPathFlag = flag.String("pythonpath", "", "Path to Python source directory containing mcp_gateway")
		dbFlag        = flag.String("db", "", "Path to SQLite database file")
		clientIDFlag  = flag.String("client-id", "", "Authenticated AI client identifier")
		versionFlag   = flag.Bool("version", false, "Print version information")
	)
	flag.Parse()

	if *versionFlag {
		fmt.Println("mcp-gateway-adapter v0.6.0 (MCP Protocol 2026-07-28)")
		os.Exit(0)
	}

	bridgeConfig := DefaultBridgeConfig()
	if *pythonFlag != "" {
		bridgeConfig.PythonBin = *pythonFlag
	}
	if *pythonPathFlag != "" {
		bridgeConfig.PythonPath = *pythonPathFlag
	}
	if *dbFlag != "" {
		bridgeConfig.DBPath = *dbFlag
	}
	if *clientIDFlag != "" {
		bridgeConfig.ClientID = *clientIDFlag
	} else if envClient := os.Getenv("MCP_CLIENT_ID"); envClient != "" {
		bridgeConfig.ClientID = envClient
	}

	ctx, cancel := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer cancel()

	state := NewAdapterState()
	info, err := bridgeConfig.CheckBridgeCompatibility(ctx)
	if err != nil {
		log.Printf("[WARN] Bridge compatibility check failed: %v", err)
		state.SetReady(false, fmt.Sprintf("ADAPTER_NOT_READY: %v", err), info)
	} else {
		log.Printf("[INFO] Bridge compatibility verified (Core API v%d, Bridge API v%d, Gateway v%s)", info.CoreAPIVersion, info.BridgeAPIVersion, info.GatewayVersion)
		state.SetReady(true, "ready", info)
	}

	server := NewGatewayServer(bridgeConfig, state)

	switch *transportFlag {
	case "stdio":
		if err := RunStdio(ctx, server); err != nil {
			log.Fatalf("Stdio server terminated with error: %v", err)
		}
	case "http":
		if err := RunHTTP(ctx, server, *bindFlag, state, bridgeConfig); err != nil {
			log.Fatalf("HTTP server terminated with error: %v", err)
		}
	default:
		log.Fatalf("Unknown transport mode: %s. Supported: stdio, http", *transportFlag)
	}
}
