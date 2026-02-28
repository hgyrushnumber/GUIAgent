import argparse
import asyncio
from pathlib import Path
import os

from pcguiagent.bootstrap import Bootstrap
from pcguiagent.utils.logger import configure_global_logging, get_logger
from pcguiagent.utils.config_loader import find_config_file

logger = get_logger("Main")


def parse_args():
    parser = argparse.ArgumentParser(description="OSWorld Optimized Agent")
    parser.add_argument("--config", type=str, default="config.yaml", help="Config file path")
    parser.add_argument("--goal", type=str, required=True, help="Agent task goal")
    parser.add_argument("--log-level", type=str, default="INFO", help="Log level (DEBUG, INFO, WARNING, ERROR)")
    return parser.parse_args()


async def async_main():
    args = parse_args()
    
    # Find config file with path resolution
    try:
        config_file_path = find_config_file(args.config, module_dir=Path(__file__).parent)
    except FileNotFoundError as e:
        # Log error before logging is configured, use print
        print("=" * 80)
        print("ERROR: Config file not found")
        print("=" * 80)
        print(str(e))
        print("\nPlease ensure config.yaml exists in one of the following locations:")
        print(f"  1. Current directory: {os.getcwd()}/config.yaml")
        print(f"  2. Module directory: {Path(__file__).parent}/config.yaml")
        print("=" * 80)
        import sys
        sys.exit(1)
    
    # Load config first to get log settings
    from pcguiagent.core.config import Config
    import yaml
    with open(config_file_path, 'r', encoding='utf-8') as f:
        config_data = yaml.safe_load(f)
    config = Config.from_dict(config_data)
    
    # Configure logging - use config if available, otherwise use args
    log_level = args.log_level or config.logging.get("level", "INFO")
    log_file = config.logging.get("file")  # Can be None to auto-generate
    
    # Configure logging with auto file generation
    actual_log_file = configure_global_logging(
        log_level=log_level,
        log_file=log_file,
        auto_generate_log_file=True,  # Always auto-generate if not specified
        log_dir="logs"  # Default log directory
    )
    
    logger.info("=" * 80)
    logger.info("PC GUI Agent - OSWorld Optimized")
    logger.info("=" * 80)
    logger.info(f"Goal: {args.goal}")
    logger.info(f"Config: {config_file_path}")
    logger.info(f"Log Level: {log_level}")
    if actual_log_file:
        logger.info(f"Log File: {actual_log_file}")

    try:
        # Use PCGuiAgent as unified entry point
        logger.info("Initializing agent...")
        from pcguiagent.agent import PCGuiAgent
        agent = PCGuiAgent(config_path=str(config_file_path))
        await agent.initialize()
        logger.info("Agent system initialized successfully")

        # Run task using unified interface
        logger.info("Starting task execution...")
        result = await agent.run(args.goal)

        # Print summary
        logger.info("=" * 80)
        logger.info("Task Execution Summary")
        logger.info("=" * 80)
        logger.info(f"Success: {result.get('success', False)}")
        logger.info(f"Steps: {result.get('step_count', 0)}")
        
        if 'metrics' in result:
            metrics = result['metrics']
            logger.info(f"Tool Invocation Rate (TIR): {metrics.get('tool_invocation_rate', 0):.2f}%")
            logger.info(f"MCP Calls: {metrics.get('mcp_tool_calls', 0)}")
            logger.info(f"Success Rate: {metrics.get('mcp_success_rate', 0):.2f}%")
        
        if 'osworld_metrics' in result:
            osworld = result['osworld_metrics']
            logger.info(f"OSWorld Acc: {osworld.get('acc', 0):.2f}")
            logger.info(f"OSWorld TIR: {osworld.get('tir', 0):.2f}%")
            logger.info(f"OSWorld ACS: {osworld.get('acs', 0)}")
        
        print("\n===== Task Result =====")
        print(result)
        print("=======================\n")

        # Graceful shutdown
        logger.info("Shutting down agent system...")
        await agent.close()
        logger.info("Agent system shutdown complete")
        
    except Exception as e:
        logger.error(f"Fatal error: {type(e).__name__}: {str(e)}", exc_info=True)
        raise


if __name__ == "__main__":
    asyncio.run(async_main())
