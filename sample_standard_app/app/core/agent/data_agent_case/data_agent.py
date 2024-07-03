# !/usr/bin/env python3
# -*- coding:utf-8 -*-

# @Time    : 2024/7/1 15:50
# @Author  : wangchongshi
# @Email   : wangchongshi.wcs@antgroup.com
# @FileName: data_agent.py
from typing import Tuple, List

from agentuniverse.agent.agent import Agent
from agentuniverse.agent.agent_manager import AgentManager
from agentuniverse.agent.input_object import InputObject
from agentuniverse.agent.output_object import OutputObject
from agentuniverse.base.util.logging.logging_util import LOGGER
from sample_standard_app.app.util.jsonl_file_utils import JsonFileWriter, JsonFileReader

from sample_standard_app.app.util.txt_file_utils import TxtFileReader


class DataAgent(Agent):
    """Data Agent class."""

    def input_keys(self) -> list[str]:
        """Return the input keys of the Agent."""
        return ['dataset_path']

    def output_keys(self) -> list[str]:
        """Return the output keys of the Agent."""
        return ['prompt_answer_list', 'eval_report_list']

    def parse_input(self, input_object: InputObject, agent_input: dict) -> dict:
        """Agent parameter parsing.

        Args:
            input_object (InputObject): input parameters passed by the user.
            agent_input (dict): agent input preparsed by the agent.
        Returns:
            dict: agent input parsed from `input_object` by the user.
        """
        agent_input['dataset_path'] = input_object.get_data('dataset_path')
        agent_input['turn'] = input_object.get_data('turn', 1)
        return agent_input

    def parse_result(self, planner_result: dict) -> dict:
        """Planner result parser.

        Args:
            planner_result(dict): Planner result
        Returns:
            dict: Agent result object.
        """
        return planner_result

    def execute(self, input_object: InputObject, agent_input: dict):
        """Execute agent instance.

        Args:
            input_object (InputObject): input parameters passed by the user.
            agent_input (dict): agent input parsed from `input_object` by the user.
        """
        # step1: collect q&a dataset from the candidate agent which needs to be evaluated.
        prompt_answer_list = self.collect_dataset(input_object, agent_input)
        input_object.add_data('prompt_answer_list', prompt_answer_list)

        LOGGER.info("-------------------------------------------")
        LOGGER.info("End: collect q&a dataset from the candidate agent done.")
        LOGGER.info("-------------------------------------------")

        # step2: write the q&a dataset to json file.
        for i in range(len(prompt_answer_list)):
            one_turn_prompt_answer_list = prompt_answer_list[i]
            json_writer = JsonFileWriter(f'data_agent_turn_{i + 1}_dataset')
            json_writer.write_json_prompt_answer_list(one_turn_prompt_answer_list)
        LOGGER.info(f"Progress: write the q&a dataset to local jsonl files.")

        # step3: evaluate q&a datasets generated by the candidate agent and generate evaluation report.
        eval_report_list = self.eval_agent(input_object)
        return {'prompt_answer_list': prompt_answer_list, 'eval_report_list': eval_report_list}

    def collect_dataset(self, input_object: InputObject, agent_input: dict) -> List[List[Tuple[str, str]]]:
        """Collect q&a dataset from the candidate agent which needs to be evaluated."""

        candidate_agent_name = self.agent_model.plan.get('planner', {}).get('candidate', '')
        # get the candidate agent which needs to be evaluated
        candidate_agent: Agent = AgentManager().get_instance_obj(candidate_agent_name)
        if not candidate_agent:
            raise ValueError('The agent instance corresponding to `candidate` parameter is empty')

        # init jsonl file reader
        jsonl_file_reader = JsonFileReader(agent_input.get('dataset_path'))
        # read query list
        query_list = jsonl_file_reader.read_json_obj_list()
        if not query_list:
            raise ValueError('query list information read from dataset_path is empty')

        prompt_answer_list = []
        for i in range(agent_input.get('turn')):
            LOGGER.info("-------------------------------------------")
            LOGGER.info(f"Start: collect q&a dataset from the candidate agent `{candidate_agent_name}`, turn {i + 1}.")
            one_turn_prompt_answer_list = []
            # single turn query and answer processing.
            for j in range(len(query_list)):
                query_dict: dict = query_list[j]
                if query_dict:
                    # init the input and output key in agent
                    first_input_key = candidate_agent.input_keys()[0]
                    first_output_key = candidate_agent.output_keys()[0]
                    # run the target agent
                    output_object: OutputObject = candidate_agent.run(**query_dict)
                    # note: the first index of input_keys and output_keys is identified as the prompt and answer.
                    one_turn_prompt_answer_list.append(
                        (query_dict.get(first_input_key, ''), output_object.get_data(first_output_key)))
                    LOGGER.info(f"Progress: the turn {i + 1} query line {j + 1} has generated the answer "
                                f"successfully.")
            LOGGER.info(f"End: the turn {i + 1} has generated the answer successfully.")
            # collect q&a dataset
            prompt_answer_list.append(one_turn_prompt_answer_list)
        return prompt_answer_list

    def eval_agent(self, input_object: InputObject):
        """Evaluate q&a datasets generated by the candidate agent and generate evaluation report."""

        planner = self.agent_model.plan.get('planner', {})
        eval_agent: Agent = AgentManager().get_instance_obj(planner.get('evaluator'))
        if eval_agent is None:
            raise ValueError('The agent instance corresponding to `evaluator` parameter is empty')
        output: OutputObject = eval_agent.run(**input_object.to_dict())
        return output.get_data('eval_report_json_list', [])
