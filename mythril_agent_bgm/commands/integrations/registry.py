#!/usr/bin/env python3
"""
Registry for AI tool integrations.
"""

from typing import List, Type

from mythril_agent_bgm.commands.integrations import AIToolIntegration
from mythril_agent_bgm.commands.integrations.claude import ClaudeIntegration
from mythril_agent_bgm.commands.integrations.cursor_agent import CursorAgentIntegration
from mythril_agent_bgm.commands.integrations.gemini import GeminiIntegration
from mythril_agent_bgm.commands.integrations.opencode import OpenCodeIntegration


class IntegrationRegistry:
    """
    Registry for managing AI tool integrations.

    To add a new integration:
    1. Create a new file in mythril_agent_bgm/commands/integrations/
    2. Implement AIToolIntegration abstract class
    3. Register it in _integrations list below
    """

    # Register all available integrations here
    _integrations: List[Type[AIToolIntegration]] = [
        ClaudeIntegration,
        CursorAgentIntegration,
        GeminiIntegration,
        OpenCodeIntegration,
    ]

    @classmethod
    def get_all_integrations(cls) -> List[AIToolIntegration]:
        """
        Get all registered integration instances.

        Returns:
            List of integration instances
        """
        return [integration_class() for integration_class in cls._integrations]

    @classmethod
    def get_integration_by_id(cls, tool_id: str) -> AIToolIntegration:
        """
        Get integration instance by tool ID.

        Args:
            tool_id: Tool identifier (e.g., 'claude')

        Returns:
            Integration instance

        Raises:
            ValueError: If tool_id is not found
        """
        for integration in cls.get_all_integrations():
            if integration.get_tool_info()[0] == tool_id:
                return integration

        raise ValueError(f"Unknown AI tool: {tool_id}")
