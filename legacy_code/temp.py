from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from pydantic import BaseModel, Field
from langgraph.graph.message import AnyMessage, add_messages
from typing import Literal, Annotated
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from typing import TypedDict, List
from openai import OpenAI
from langchain_openai import ChatOpenAI
from langgraph.store.memory import InMemoryStore
from typing_extensions import TypedDict
from langchain_core.runnables import RunnableConfig
from langgraph.store.base import BaseStore
from portkey_ai import Portkey, createHeaders, PORTKEY_GATEWAY_URL
from portkey_ai.langchain import LangchainCallbackHandler
from langchain_anthropic import ChatAnthropic

import os
import yaml, uuid
import json
from datetime import datetime
import pandas as pd
import sqlite3
from typing import List, Dict
from pathlib import Path

from dotenv import load_dotenv, find_dotenv
_ = load_dotenv(find_dotenv())
openai_api_key = os.getenv("OPENAI_API_KEY")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY")
PORTKEY_API_KEY = os.getenv("PORTKEY_API_KEY")
PORTKEY_VIRTUAL_KEY = os.getenv("PORTKEY_VIRTUAL_KEY")
PORTKEY_VIRTUAL_KEY_A = os.getenv("PORTKEY_VIRTUAL_KEY_A")

def load_prompts(file_path='prompts.yaml'):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

prompts = load_prompts()

# define memory object
in_memory_store = InMemoryStore()

# PORTKEY IMPLEMENTATION
portkey_handler = LangchainCallbackHandler(
    api_key=PORTKEY_API_KEY,
    metadata={
        "session_id": "session_1",  # Use consistent metadata across your application
        "agent_id": "Router_Agent",  # Specific to the current agent
    }
)
# Initialize OpenAI model
# model = llm
# model = ChatOpenAI(model="gpt-4o", max_tokens=50, temperature=0.9, max_retries=2)
model = ChatOpenAI(
    api_key=openai_api_key,
    model="gpt-4o",
    max_retries=2,
    temperature=0.9,
    max_tokens=150,
    base_url=PORTKEY_GATEWAY_URL,
    default_headers=createHeaders(
        api_key=PORTKEY_API_KEY,
        virtual_key=PORTKEY_VIRTUAL_KEY, # Pass your virtual key saved on Portkey for any provider you'd like (Anthropic, OpenAI, Groq, etc.). if using this, no need to pass openai api key
        config = "pc-sukoon-86ab23"
    ),
    callbacks=[portkey_handler],
)
# max_completion_tokens = 200 for o1 models

# model_a = ChatAnthropic(model="claude-3-5-haiku-20241022", temperature=0.9, api_key=anthropic_api_key, max_tokens = 200, max_retries=2) 
# to use sonnet 3.5, put claude-3-5-sonnet-20241022 as model
model_a = ChatOpenAI(
    api_key=anthropic_api_key, # We'll pass a dummy API key here
    base_url=PORTKEY_GATEWAY_URL,
    default_headers=createHeaders(
        api_key=PORTKEY_API_KEY,
        virtual_key=PORTKEY_VIRTUAL_KEY_A, # Pass your virtual key saved on Portkey for any provider you'd like (Anthropic, OpenAI, Groq, etc.)
        provider="anthropic",
        # anthropic_beta="prompt-caching-2024-07-31", # to add cache, add "cache_control": {"type": "ephemeral"} in respective message body
    ),
    model="claude-3-5-sonnet-latest", #claude-3-5-haiku-20241022
    temperature=0.9,
    max_tokens = 150,
    max_retries=2,
)

# LANGGRAPH IMPLEMENTATION STARTS
# Define the state
class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]

# Create the base Agent class
class Agent:
    def __init__(self, prompt_template, model, store: BaseStore):
        self.prompt_template = prompt_template
        self.model = model
        self.store = store
        self.namespace = ("memories", "123")  # Using the same namespace across agents
        # Clear memory when a new object is created
        for key in list(self.store.store.keys()):
            if key[0] == self.namespace[0] and key[1] == self.namespace[1]:
                del self.store.store[key]
    
    def run(self, state: State):
        print(f"Running {self.__class__.__name__}")
        # Retrieve the last 6 memories if available
        memories = self.store.search(self.namespace)
        last_memories = memories[-6:] if len(memories) > 6 else memories
        info = "\n".join([d.value["data"] for d in last_memories])
        # Incorporate memories into the system message
        system_msg = self.prompt_template.format(input="{input}") + f"\nTake into account these past conversations: {info}"
        response = self.model.invoke(
            [{"type": "system", "content": system_msg}] + state["messages"]
        )
        # Store new memories unconditionally or based on specific criteria
        # last_message = state["messages"][-1]
        # if "remember" in last_message.content.lower():
        memory = str(response)
        self.store.put(self.namespace, str(uuid.uuid4()), {"data": memory})
        return {"messages": response}

# DEFINING THE PROMPT

planner_prompt = ChatPromptTemplate.from_messages([
    ("system", prompts['planner_agent_prompt']),
    ("human", "{input}"),
])

conversational_prompt = ChatPromptTemplate.from_messages([
    ("system", prompts['empathetic_agent_prompt']),
    ("human", "{input}"),
])

suicide_prevention_prompt = ChatPromptTemplate.from_messages([
    ("system", prompts['suicide_prevention_agent_prompt']),
    ("human", "{input}"),
])

anger_management_prompt = ChatPromptTemplate.from_messages([
    ("system", prompts['anger_prevention_agent_prompt']),
    ("human", "{input}"),
])

motivational_prompt = ChatPromptTemplate.from_messages([
    ("system", prompts['motivational_agent_prompt']),
    ("human", "{input}"),
])

dialectical_behavior_therapy_prompt = ChatPromptTemplate.from_messages([
    ("system", prompts['dbt_agent_prompt']),
    ("human", "{input}")
])

cognitive_behavioral_therapy_prompt = ChatPromptTemplate.from_messages([
    ("system", prompts['cbt_agent_prompt']),
    ("human", "{input}")
])

# Define subclasses for each specific agent
class ConversationalAgent(Agent):
    pass  # Inherits from Agent
class SuicidePreventionAgent(Agent):
    pass  # Inherits from Agent
class AngerManagementAgent(Agent):
    pass  # Inherits from Agent
class MotivationalAgent(Agent):
    pass  # Inherits from Agent
class DialecticalBehaviorTherapyAgent(Agent):
    pass  # Inherits from Agent
class CognitiveBehavioralTherapyAgent(Agent):
    pass  # Inherits from Agent

# Initialize agent instances with their respective prompts and models
conversational_agent = ConversationalAgent(conversational_prompt, model, in_memory_store)
suicide_prevention_agent = SuicidePreventionAgent(suicide_prevention_prompt, model_a, in_memory_store)
anger_management_agent = AngerManagementAgent(anger_management_prompt, model_a, in_memory_store)
motivational_agent = MotivationalAgent(motivational_prompt, model_a, in_memory_store)
dbt_agent = DialecticalBehaviorTherapyAgent(dialectical_behavior_therapy_prompt, model_a, in_memory_store)
cbt_agent = CognitiveBehavioralTherapyAgent(cognitive_behavioral_therapy_prompt, model_a, in_memory_store)


# Define router
# Define the router
def route_query(state: State):
    class RouteQuery(BaseModel):
        """Route a user query to the most relevant node based on the emotional or psychological state."""
        route: Literal[
            "conversational", "suicide_prevention", "anger_management", 
            "motivational", "dialectical_behavior_therapy", "cognitive_behavioral_therapy", "denial"
        ] = Field(
            ...,
            description=(
                "Think step by step and direct to the most appropriate agent."
            )
        )
    structured_llm_router = model.with_structured_output(RouteQuery)
    question_router = planner_prompt | structured_llm_router
    last_message = state["messages"][-1]
    resp = question_router.invoke({"input": last_message})
    return resp.route

# Create a custom graph class to handle agents
class AgentStateGraph(StateGraph):
    def __init__(self, state_type):
        super().__init__(state_type)
        # Dictionary to hold agents
        self.agents = {
            "conversational": conversational_agent,
            "suicide_prevention": suicide_prevention_agent,
            "anger_management": anger_management_agent,
            "motivational": motivational_agent,
            "dialectical_behavior_therapy": dbt_agent,
            "cognitive_behavioral_therapy": cbt_agent,
            "denial": None  # Special case for denial
        }
    
    def add_agent_node(self, name: str):
        def agent_runner(state: State):
            agent = self.agents[name]
            if agent:
                return agent.run(state)
            else:
                # Handle 'denial' agent separately
                return {"messages": [AIMessage(content="Please use this wisely. This space is for mental and emotional well-being. Namaste.")]}
        self.add_node(name, agent_runner)

def run_denial_agent(state: State):
    return {"messages": "Please use this wisely. This space is for mental and emotional well-being. Namaste."}
    # no need to invoke model here as we're just denying the request here

# Instantiate the graph
workflow = AgentStateGraph(State)

# Add nodes for each agent
agent_names = [
    "conversational",
    "suicide_prevention",
    "anger_management",
    "motivational",
    "dialectical_behavior_therapy",
    "cognitive_behavioral_therapy",
    "denial"
]


for agent_name in agent_names:
    workflow.add_agent_node(agent_name)

# Add edges
workflow.add_conditional_edges(
    START,
    route_query,
    {name: name for name in agent_names}
)
for agent_name in agent_names:
    workflow.add_edge(agent_name, END)

# Compile the graph
memory = MemorySaver()
graph = workflow.compile(checkpointer=memory)

# Function to run a conversation turn
def chat(message: str, config: dict):
    result = graph.invoke({"messages": [HumanMessage(content=message)]}, config=config)
    return result["messages"][-1]

if __name__ == "__main__":
    config = {"configurable": {"thread_id": "1"}}
    while True:
        user_input = input("You: ")
        if user_input.lower() in ["exit", "quit"]:
            print("Sukoon: Goodbye!")
            break
        response = chat(user_input, config)
        print("Sukoon:", response.content)      
        
# # Define all agents
# def run_conversational_agent(state: State, store: BaseStore):
#     print("Running conversational agent")
#     namespace = ("memories", "123")
#     memories = store.search(namespace)
#     info = "\n".join([d.value["data"] for d in memories])
#     system_msg = f"{conversational_prompt} \n Take into account these past conversations: {info}"
#     response = model.invoke(
#         [{"type": "system", "content": system_msg}] + state["messages"]
#     )
#     # new_conversational_prompt = f"{conversational_prompt} \n Take into account these past conversation into account: {info}"
#     # convo_model = new_conversational_prompt | model
#     # response = convo_model.invoke(state["messages"])
    
#     # Store new memories if the user asks the model to remember
#     last_message = state["messages"][-1]
#     if "remember" in last_message.content.lower() or True: # rn defaults to True in all cases
#         memory = str(response)
#         store.put(namespace, str(uuid.uuid4()), {"data": memory})
#         # store.put(namespace, str(uuid.uuid4()), {"data": memory})
#     return {"messages": response}

# def run_suicide_prevention_agent(state: State):
#     print("Running suicide prevention agent")
#     concern_model = suicide_prevention_prompt | model_a # model
#     response = concern_model.invoke(state["messages"])
#     return {"messages": response}

# def run_anger_management_agent(state: State):
#     print("Running anger management agent")
#     anger_model = anger_management_prompt | model_a # model
#     response = anger_model.invoke(state["messages"])
#     return {"messages": response}

# def run_motivational_agent(state: State):
#     print("Running motivational agent")
#     motivation_model = motivational_prompt | model_a # model
#     response = motivation_model.invoke(state["messages"])
#     return {"messages": response}

# def run_dialectical_behavior_therapy_agent(state: State):
#     print("Running dialectical_behavior_therapy agent")
#     dialectical_behavior_therapy_model = dialectical_behavior_therapy_prompt | model_a # model
#     response = dialectical_behavior_therapy_model.invoke(state["messages"])
#     return {"messages": response}

# def run_cognitive_behavioral_therapy_agent(state: State):
#     print("Running cognitive_behavioral_therapy agent")
#     cognitive_behavioral_therapy_model = cognitive_behavioral_therapy_prompt | model_a # model
#     response = cognitive_behavioral_therapy_model.invoke(state["messages"])
#     return {"messages": response}

# # Add nodes for each agent
# workflow.add_node("conversational", run_conversational_agent)
# workflow.add_node("suicide_prevention", run_suicide_prevention_agent)
# workflow.add_node("anger_management", run_anger_management_agent)
# workflow.add_node("motivational", run_motivational_agent)
# # workflow.add_node("mindfulness", run_mindfulness_agent)
# workflow.add_node("dialectical_behavior_therapy", run_dialectical_behavior_therapy_agent)
# workflow.add_node("cognitive_behavioral_therapy", run_cognitive_behavioral_therapy_agent)
# workflow.add_node("denial", run_denial_agent)

# Add edges
# workflow.add_conditional_edges(
#     START,
#     route_query,
#     {
#         "conversational": "conversational",
#         "suicide_prevention": "suicide_prevention",
#         "anger_management": "anger_management",
#         "motivational": "motivational",
#         # "mindfulness": "mindfulness",
#         "dialectical_behavior_therapy": "dialectical_behavior_therapy",
#         "cognitive_behavioral_therapy": "cognitive_behavioral_therapy",
#         "denial": "denial"
#     }
# )

# workflow.add_edge("conversational", END)
# workflow.add_edge("suicide_prevention", END)
# workflow.add_edge("anger_management", END)
# workflow.add_edge("motivational", END)
# # workflow.add_edge("mindfulness", END)
# workflow.add_edge("dialectical_behavior_therapy", END)
# workflow.add_edge("cognitive_behavioral_therapy", END)
# workflow.add_edge("denial", END)

