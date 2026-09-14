"""Opt-in real Ollama RAG/memory smoke test using disposable synthetic data."""
import asyncio
import os
import tempfile
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from school_ai.database.base import Base
from school_ai.demo_seed import seed_demo_data
from school_ai.services import SchoolDataService, SchedulingService
from school_ai.services.conversations import ConversationService
from school_ai.services.policies import PolicyService
from school_ai.repositories import SchoolDataRepository, ScheduleRepository, SchedulingDataRepository
from school_ai.mcp.server import SchoolMCPServer
from school_ai.mcp.client import InProcessMCPClient
from school_ai.ai.harness import AIHarness
from school_ai.ai.context import ContextSettings
from school_ai.ai.providers.ollama import OllamaProvider

async def main():
    with tempfile.TemporaryDirectory(prefix='school-ai-real-smoke-') as directory:
        engine = create_engine(f'sqlite:///{directory}/smoke.db')
        Base.metadata.create_all(engine)
        sessions = sessionmaker(engine, expire_on_commit=False)
        with sessions() as session:
            seed_demo_data(session)
        policies = PolicyService(sessions)
        policies.ingest_directory(Path('demo_data/policies'))
        conversations = ConversationService(sessions, ContextSettings(recent_turns=1))
        credential = conversations.create()
        for prompt in (
            'Remember that my class is Year 7 Aurora. Acknowledge briefly.',
            'What is the lunch policy? Cite the source.',
            'Which class did I ask you to remember?',
        ):
            with sessions() as session:
                server = SchoolMCPServer(SchoolDataService(SchoolDataRepository(session)),
                    SchedulingService(ScheduleRepository(session), SchedulingDataRepository(session)), policies)
                agent = AIHarness(OllamaProvider(os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434'), os.getenv('OLLAMA_MODEL', 'qwen2.5:3b')),
                    InProcessMCPClient(server, after_tool=session.close))
                print('PROMPT:', prompt, flush=True)
                result = await conversations.chat(credential['id'], credential['access_token'], prompt, agent)
                print('ANSWER:', result.assistant_text, flush=True)
                print('TOOLS:', [tool.name for tool in result.tool_calls], 'MEMORY:', result.metadata.get('memory_compressed'),
                      'COMPRESSION_FAILED:', result.metadata.get('compression_failed'), flush=True)
                if 'lunch' in prompt:
                    assert result.metadata.get('sources'), 'No policy citations'
                if 'Which class' in prompt:
                    assert 'Aurora' in result.assistant_text, 'Failed to recall the class'
                    assert result.metadata.get('memory_compressed'), 'Memory was not compressed'
        assert len(conversations.read(credential['id'], credential['access_token'])['turns']) == 3
        engine.dispose()
        print('REAL OLLAMA CONTEXT SMOKE PASSED', flush=True)

if __name__ == "__main__":
    asyncio.run(main())
