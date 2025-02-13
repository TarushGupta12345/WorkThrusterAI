import getpass
import os

os.environ["OPENAI_API_KEY"] = "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"

from langchain_openai import ChatOpenAI

model = ChatOpenAI(model="gpt-4o-mini")

from langgraph.graph import StateGraph, MessagesState, END, START
from typing import TypedDict, List, Dict, Any, Literal, Annotated, Sequence, Tuple
import math, random
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langgraph.graph import END, StateGraph, START
import operator
from langchain_openai import ChatOpenAI
from langchain_core.messages import AIMessage
import functools
from langgraph.prebuilt import ToolNode
import copy
import json
from langchain_core.prompts import PromptTemplate
from datetime import date
import emailGetter
import IPython

class GraphState(TypedDict):
    #emails: Dict[email text, Dict[snippet, list of todos]]
    emails: Dict[str, Dict[str, List[str]]]
    
    #the duration that the user wants to index from
    datePrefs: date

    #if the user is new or not
    userNew: str

    #userpreferences: user preferences
    userPreferences: str

    #completed todos
    completedTodos: Dict[str, Dict[str, List[str]]]

    #current agent
    currentAgent: str


def create_general_agent(state, llm):

    userNew = state.get("userNew")

    system_prompt_text = """
    You are a chatbot for WorkThruster AI.
    Your job is to answer any questions the user has about your features, and to identify the timeframe that the user wants to consider.

   WorkThruster AI's features are:
       - **Email Analysis**: Extract snippets from emails to identify tasks.
       - **To-Do Generation**: Create structured to-do lists from extracted snippets.
       - **Source Linking**: Associate each task with its source email for clarity.
       

    ### Guidelines:

    The user is new: {userNew}

    If the user **is new**:
    1. Greet the user (if not already done). Tell them about the pipeline's features.

    If the user **is not new**:
    1. Greet the user (if not already done). Do not tell them about the pipeline's features UNLESS ASKED.

    2. Ask the user the date they want their emails pulled until. Some options you could offer them are:
      - 1 day
      - 1 week
      - 2 weeks
      etc.

    3. When the user has chosen this date, say the exact following: "Got it! Working to identify your relevant emails now. //API"

    **NOTE: DO NOT GENERATE TODOS!** If asked (and the context for the email timeframe is not provided), respond with something along the lines of "Got it, let's identify the timeframe first" and move to step number two.

    ### Inputs:
    - **Last User Prompt**: {user_input}
    - **Conversation History**: {conversation_history}
    """
    system_prompt = PromptTemplate(template=system_prompt_text, input_variables=["conversation_history", "user_input", "userNew"])
    chain = system_prompt | llm
    conversation_history = ""

    while True:
        if conversation_history == "": user_input = ""
        else: user_input = input("\nEnter your message here:   ")
        conversation_history += f"\nUser: {user_input}"

        raw_response = chain.invoke({"conversation_history": conversation_history, "user_input": user_input, "userNew":userNew})
        llm_response = raw_response.content if hasattr(raw_response, "content") else str(raw_response)

        conversation_history += f"\nWorkThruster: {llm_response}"

        if "//API" in llm_response:
            cleaned_response = llm_response.replace("//API", "").strip()
            print(f"WorkThruster: {cleaned_response}")
            return {"currentAgent": "APIAgent", "datePrefs": cleaned_response}
        print(f"WorkThruster: {llm_response}")
general_agent = functools.partial(create_general_agent, llm=model)

def create_api_call_agent(state, llm):
  """Create an agent."""

  today = date.today().strftime("%Y-%m-%d").replace("-", "/")
  
  system_prompt_text = '''
  Given a duration (for instance, two weeks), your job is to return the number of days in that duration ONLY. 
  Do not say anything other than this number.

  ### Inputs:
  - **Duration**: {duration}
  '''

  system_prompt = str(PromptTemplate(template=system_prompt_text, input_variables=["datePrefs"]))
  
  messages = load_messages_from_file(system_prompt, today)
  
  emails = state["emails"]
  completedTodos = state["completedTodos"]
  
  for message in messages:
    emails[message] = {}
    completedTodos[message] = {}
  
  return {'emails':emails, "completedTodos":completedTodos, "previousDate":system_prompt, "currentAgent":"userPreferencesAgent"}
api_call_agent = functools.partial(create_api_call_agent, llm=model)

def load_messages_from_file():
    # Simulated API Call.
    if os.path.exists('messages.json'):
      try:
        data = json.load(open('messages.json', 'r'))
      except Exception as e:
        print("missing messages.json... either email API code or some other bug")
        return {}

    messages = []
    for key in data.keys():
      thread = []
      for email in key:
        checker = False

        fromstr = "from: " + email["from"]
        tostr = "to: " + email["to"]
        datestr = "date: " + email["dateTime"]
        subjectstr = "subject: " + email["subject"]
        bodystr = "body: " + email["body"]

        message = fromstr + "\n " + tostr + "\n" + datestr + "\n" + subjectstr + "\n" + bodystr + "\n\n"
        thread.append(message)
      messages.append(thread)
    try:  
      return messages
    except Exception as e:
       print("messages is null, check EmailGetter code for more information")
       return
        
def create_user_preferences_agent(state, llm):
    longtimePrefs = state.get("longtimePrefs")
    userNew = state.get("userNew")

    #note: the longtime prefs are not being modified. I need to connect another agent (to avoid overloading on context) where the longterm preferences are being updated/add a checker to identify if the prefs should be updated.

    system_prompt_text = """
    You are a chatbot for WorkThruster AI, designed to help users organize tasks and workflows effectively.

    The agent before you has already identified the emails neccesary and the user has decided to generate todos.
    Continue the conversation from this point.

    Your role is to ask if the user has any specific preferences on how they would like their todos to be generated.

    ###Context:
    1. The overall pipeline's format is this:
        - **Email Analysis**: Extract snippets from emails to identify tasks.
        - **To-Do Generation**: Create structured to-do lists from extracted snippets.
        - **Source Linking**: Associate each task with its source email for clarity.

    2. As such, your preferences are limited to the actual generation, not prioritization/notification. Some example preferences you can provide are:
        - **Grouping**: Grouping the todos by date, email, context, etc.
        - **Snippet Focus**: Focusing on specific information within the emails (i.e. "focus the snippets on logistics")
        - **Todo Focus**: Focusing on specific information within the todos (i.e. "make the todos actionable, with dates involved")

    ##Guidelines:
    The user is new: {userNew}

    If the user is new:
    1. Ask the user something along the lines of: "Do you have any specific preferences on how you would like snippets to be identified? If needed, I can provide examples."
    2. Provide examples of preferences based on context if asked.
    3. Whenever you think the user has completely entered their preferences, briefly summarize their preferences and ask for confirmation, and append "//UPREFS" to the end of your message.
    4. Once the user has confirmed, return only the words: "Got it! Working to identify snippets now. //TODO"
    5. IF the user does not give confirmation, please continue to work with the user to identify their preferences.

    If the user is not new:
    1. Print out the previous preferences of the user and ask if you should just use these.
    Prefs: {longtimePrefs}
    (if there are no prefs entered, the user is new; proceed from step 1 of the new user protocol).
    2. If the user does not want to use previous preferences, go to the "new user steps" and continue from step 2.

    NOTE: DO NOT GENERATE TODOS! If the user asks to generate todos, route them using Guideline #4 after they have finished with their preferences.

    ### Inputs:
    - **Last User Prompt**: {user_input}
    - **Conversation History**: {conversation_history}
    """
    system_prompt = PromptTemplate(template=system_prompt_text, input_variables=["conversation_history", "user_input", "userNew", "longtimePrefs"])
    chain = system_prompt | llm
    conversation_history = ""
    userPrefs = ""
    checker = longtimePrefs == ""
    while True:
        if conversation_history == "": user_input = ""
        else: user_input = input("\nEnter your message here:   ")
        conversation_history += f"\nUser: {user_input}"
        raw_response = chain.invoke({"conversation_history": conversation_history, "user_input": user_input, "userNew":userNew, "longtimePrefs":longtimePrefs})
        llm_response = raw_response.content if hasattr(raw_response, "content") else str(raw_response)
        conversation_history += f"\nWorkThruster: {llm_response}"

        if "//UPREFS" in llm_response:
            cleaned_response = llm_response.replace("//UPREFS", "").strip()
            print(f"WorkThruster: {cleaned_response}")
            userPrefs = cleaned_response
        elif "//TODO" in llm_response:
            cleaned_response = llm_response.replace("//TODO", "").strip()
            print(f"WorkThruster: {cleaned_response}")
            if checker:
              return {"currentAgent": "snippetIdentification", "userPreferences": userPrefs, "longtimePrefs":userPrefs}
            return {"currentAgent":"snippetIdentification", "userPreferences":userPrefs}
        else:
            print(f"WorkThruster: {llm_response}")    
user_preferences_agent = functools.partial(create_user_preferences_agent, llm=model)

