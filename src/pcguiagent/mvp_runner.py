"""CLI entrypoint for single-task MVP runner.

Usage:
  python -m src.pcguiagent.mvp_runner --demo
"""
from __future__ import annotations

import argparse
from datetime import datetime

from pcguiagent.mvp.local_model import DummyLocalClient, OpenAICompatibleLocalClient
from pcguiagent.mvp.policy import LocalModelPolicy
from pcguiagent.mvp.single_task_runner import SingleTaskMVPRunner


class DemoEnv:
    """A tiny deterministic env to validate pipeline wiring."""

    def __init__(self):
        self._step = 0

    def reset(self):
        self._step = 0
        return {
            "window_meta": {"app": "browser"},
            "url": "about:blank",
            "page_text": "",
            "a11y_nodes": [
                {"element_id": "addr", "role": "textbox", "text": "Address", "editable": True},
                {"element_id": "search", "role": "searchbox", "text": "搜索", "editable": True},
                {"element_id": "go", "role": "button", "text": "搜索", "clickable": True},
            ],
        }

    def step(self, action):
        self._step += 1
        obs = self.reset()
        if action.get("action_type") == "TYPE" and action.get("text") == "https://www.baidu.com":
            obs["url"] = "https://www.baidu.com"
            obs["page_text"] = "百度一下"
        if action.get("action_type") == "TYPE" and action.get("text") == "Python":
            obs["url"] = "https://www.baidu.com/s?wd=Python"
            obs["page_text"] = "Python - 百度搜索结果"
        done = self._step >= 8
        return obs, 0.0, done, {}


def parse_args():
    parser = argparse.ArgumentParser(description="Run single-task local-model MVP")
    parser.add_argument("--demo", action="store_true", help="Run built-in demo env")
    parser.add_argument("--endpoint", type=str, default="", help="OpenAI-compatible local endpoint")
    parser.add_argument("--model", type=str, default="local-model", help="Model name for endpoint mode")
    parser.add_argument("--log-path", type=str, default="logs/mvp_single_task.jsonl")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.endpoint:
        client = OpenAICompatibleLocalClient(base_url=args.endpoint, model=args.model)
    else:
        client = DummyLocalClient()

    policy = LocalModelPolicy(client)
    log_path = args.log_path.replace(
        ".jsonl", f"_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jsonl"
    )
    runner = SingleTaskMVPRunner(policy=policy, log_path=log_path)

    if not args.demo:
        raise ValueError("MVP runner currently ships with --demo env only in this commit.")

    result = runner.run_episode(DemoEnv())
    print({"result": result, "log_path": log_path})


if __name__ == "__main__":
    main()
