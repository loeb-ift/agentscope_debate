import asyncio
from typing import Dict, Any, List
from mars.types.artifact import ResearchPlan, Task, TaskStatus
from mars.agents.planner import PlannerAgent
from mars.agents.executor import ExecutorAgent
from api.database import SessionLocal
from api import models
from sqlalchemy.orm import Session

class Coordinator:
    """
    MARS V2 Coordinator
    Responsible for:
    1. Managing the Research Plan (Task Graph)
    2. Dispatching Tasks to Agents
    3. Collecting Artifacts and Updating State
    """
    def __init__(self, task_id: str, topic: str):
        self.task_id = task_id
        self.topic = topic
        self.plan: ResearchPlan = None
        self.status = "initialized"
        self.planner = PlannerAgent()
        self.executors = {} # Cache executors by role
        self.artifacts = [] # Collected evidence
        
    async def initialize_plan(self):
        """Calls Planner Agent to generate initial plan"""
        print(f"[{self.task_id}] Coordinator: Initializing plan for topic '{self.topic}'...")
        
        # Real Planner Call
        self.plan = await self.planner.generate_plan(self.topic)
        
        self.status = "planning_complete"
        print(f"[{self.task_id}] Plan generated with {len(self.plan.tasks)} tasks.")

    def _get_executor(self, role: str) -> ExecutorAgent:
        if role not in self.executors:
            # 1. Try to find matching V1 Agent in DB
            db = SessionLocal()
            try:
                # Fuzzy match role name
                agent = db.query(models.Agent).filter(models.Agent.name.like(f"%{role}%")).first()
                
                system_prompt = None
                allowed_tools = None
                
                if agent:
                    print(f"[{self.task_id}] Found V1 Agent for role '{role}': {agent.name}")
                    system_prompt = agent.system_prompt
                    
                    # 2. Get Agent's ToolSet
                    # Find toolset assignment
                    assignment = db.query(models.AgentToolSet).filter(models.AgentToolSet.agent_id == agent.id).first()
                    if assignment:
                        toolset = db.query(models.ToolSet).filter(models.ToolSet.id == assignment.toolset_id).first()
                        if toolset:
                            allowed_tools = toolset.tool_names
                            # Always include basic search tools just in case
                            allowed_tools.extend(["searxng.search", "duckduckgo.search", "internal.search_company"])
                            allowed_tools = list(set(allowed_tools))
            finally:
                db.close()

            # Create Executor with specialized config
            self.executors[role] = ExecutorAgent(
                name=f"{role}_Bot", 
                role=role, 
                system_prompt_template=system_prompt,
                allowed_tools=allowed_tools
            )
            
        return self.executors[role]

    async def run_next_step(self):
        """Execute the next available task in the DAG"""
        if not self.plan:
            await self.initialize_plan()
            
        # Find executable tasks (pending and deps met)
        executable_tasks = []
        completed_task_ids = {t.id for t in self.plan.tasks if t.status == TaskStatus.COMPLETED}
        
        for task in self.plan.tasks:
            if task.status == TaskStatus.PENDING:
                deps_met = all(dep_id in completed_task_ids for dep_id in task.dependencies)
                if deps_met:
                    executable_tasks.append(task)
        
        if not executable_tasks:
            # Check if really complete
            pending_count = sum(1 for t in self.plan.tasks if t.status == TaskStatus.PENDING)
            in_progress_count = sum(1 for t in self.plan.tasks if t.status == TaskStatus.IN_PROGRESS)
            
            if pending_count == 0 and in_progress_count == 0:
                print(f"[{self.task_id}] All tasks completed.")
            elif pending_count > 0:
                print(f"[{self.task_id}] Waiting for dependencies... (Pending: {pending_count}, Running: {in_progress_count})")
            return

        # Dispatch Tasks
        tasks_coroutines = []
        for task in executable_tasks:
            print(f"[{self.task_id}] Dispatching task {task.id}: {task.description} -> {task.assigned_role}")
            task.status = TaskStatus.IN_PROGRESS
            
            executor = self._get_executor(task.assigned_role)
            tasks_coroutines.append(self._execute_task_wrapper(executor, task))
            
        # Run parallel
        await asyncio.gather(*tasks_coroutines)

    async def _execute_task_wrapper(self, executor: ExecutorAgent, task: Task):
        """Wrapper to execute task and update state"""
        try:
            evidence = await executor.execute_task(task)
            self.artifacts.append(evidence)
            task.status = TaskStatus.COMPLETED
            task.output_artifact_ids.append(evidence.id)
            print(f"[{self.task_id}] Task {task.id} completed. Generated Artifact: {evidence.id}")
        except Exception as e:
            print(f"[{self.task_id}] Task {task.id} failed: {e}")
            task.status = TaskStatus.FAILED

    async def run_loop(self):
        """Main loop until completion"""
        while True:
            await self.run_next_step()
            if all(t.status == TaskStatus.COMPLETED or t.status == TaskStatus.FAILED for t in self.plan.tasks):
                print(f"[{self.task_id}] Process finished.")
                break
            # Avoid tight loop if waiting
            await asyncio.sleep(0.5)