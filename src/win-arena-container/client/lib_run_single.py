"""Script to run & evaluate agent-loop on a single example from the benchmark."""
import datetime
import json
import logging
import os
import time
import traceback
from trajectory_recorder import TrajectoryRecorder

from ufo.config.config import Config
from ufo.llm.openai import OpenAIService
from typing import Any, Union, Mapping, TypeVar, Callable, Awaitable, cast, overload

logger = logging.getLogger("desktopenv.experiment")

configs = Config.get_instance().config_data

# Open the JSON file
with open("./settings.json", "r") as file:
    # Load the JSON data from the file
    data = json.load(file)
time_limit = data["time_limit"]

def run_single_example(agent, env, example, max_steps, instruction, args, example_result_dir, scores):
    agent.reset()
    obs = env.reset(task_config=example)
    done = False
    step_idx = 0

    #env.controller.start_recording()
    start_time = datetime.datetime.now()
    
    # Initialize recorder, which will save the trajectory as a JSON & HTML in {example_result_dir}/traj.(jsonl,html)
    recorder = TrajectoryRecorder(example_result_dir)
    
    # Record initial state
    init_timestamp = start_time.strftime("%Y%m%d@%H%M%S")
    recorder.record_init(obs, example, init_timestamp)
    
    from mm_agents.server_agents.agent import ServerAgent
    if isinstance(agent, ServerAgent):
        if agent.agent_settings["llm_type"] == "azure":
            token = ""
            try:
                token_provider = OpenAIService.get_aad_token_provider(
                    aad_api_scope_base=configs["HOST_AGENT"].get("AAD_API_SCOPE_BASE", ""),
                    aad_tenant_id=configs["HOST_AGENT"].get("AAD_TENANT_ID", "")
                )
                token = token_provider()
                print(f"Got token: {token}")
                if not token or not isinstance(cast(Any, token), str):
                    raise ValueError(
                        f"Expected `azure_ad_token_provider` argument to return a string but it returned {token}",
                    )
                token = str(token)
            except Exception as e:
                print(f"Failed to get token: {e}")
            agent.agent_settings["llm_auth"]["token"] = token
        agent.agent_settings["task_name"] = example["related_apps"][0] + "/" + example["id"]
        logger.info("Agent: Running server agent %s...", agent.agent_name)
        logger.info("Agent settings: %s...", agent.agent_settings)
        response = env.controller.run_agent(agent.agent_name, instruction, agent.agent_settings)

        if response.get("status") == "failed" and env.evaluator['func'] == "infeasible":
            print(f"Agent failed in this run")
            env.step("FAIL", args.sleep_after_execution)

    else:
        while not done and step_idx < max_steps:
            if obs is None:
                logger.error("Observation is None. Waiting a little to do next step.")
                time.sleep(5)
                step_idx += 1
                continue

            logger.info("Agent: Thinking...")
            response, actions, logs, computer_update_args = agent.predict(
                instruction,
                obs
            )

            # update the computer object, used by navi's action space
            if computer_update_args:
                env.controller.update_computer(**computer_update_args)

            # step environment with agent actions 
            for action in actions:
                # Capture the timestamp before executing the action
                action_timestamp = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")
                elapsed_timestamp = f"{datetime.datetime.now() - start_time}"
                logger.info("Step %d: %s", step_idx + 1, action)

                obs, reward, done, info = env.step(action, args.sleep_after_execution)

                logger.info("Reward: %.2f", reward)
                logger.info("Done: %s", done)

                # Record step data
                recorder.record_step(
                    obs, 
                    logs,
                    step_idx,
                    action_timestamp,
                    elapsed_timestamp,
                    action,
                    reward,
                    done,
                    info
                )

                if done:
                    logger.info("The episode is done.")
                    break
            # inc step counter
            step_idx += 1
    
    logger.info("Running evaluator(s)...")
    result = env.evaluate()
    logger.info("Result: %.2f", result)
    scores.append(result)

    with open(os.path.join(example_result_dir, "result.txt"), "w", encoding="utf-8") as f:
        f.write(f"{result}\n")
    
    # Record final results
    recorder.record_end(result, start_time)
    # env.controller.end_recording(os.path.join(example_result_dir, "recording.mp4"))