#!/usr/bin/env python3
"""
Groq-Powered Pokemon MCP Client
Connects to the Pokemon MCP server and uses Groq for intelligent responses
"""

import asyncio
import json
import os
import sys
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from groq import Groq
import logging
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp import types

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("groq-pokemon-client")

@dataclass
class MCPToolResult:
    success: bool
    data: str
    error: Optional[str] = None

class GroqPokemonAssistant:
    """AI assistant powered by Groq that uses MCP for Pokémon data"""
    
    def __init__(self, groq_api_key: str, mcp_server_path: str):
        self.groq_client = Groq(api_key=groq_api_key)
        self.mcp_server_path = mcp_server_path
        self.conversation_history = []
        self.session = None
        self.exit_stack = AsyncExitStack()
        
    async def start(self):
        """Initialize the assistant and MCP connection"""
        try:
            logger.info("🔗 Starting MCP connection...")
            
            # Start the MCP server
            server_params = StdioServerParameters(
                command=sys.executable,
                args=[self.mcp_server_path],
                env=None
            )
            
            # Create stdio client using AsyncExitStack for proper resource management
            stdio_streams = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            
            if len(stdio_streams) != 2:
                raise ValueError(f"Expected 2 stdio streams, got {len(stdio_streams)}")
                
            read_stream, write_stream = stdio_streams
            
            # Create session using AsyncExitStack
            self.session = await self.exit_stack.enter_async_context(
                ClientSession(read_stream, write_stream)
            )
            
            # Initialize the session
            init_result = await self.session.initialize()
            logger.info(f"🔗 MCP Protocol version: {init_result.protocolVersion}")
            
            # Get available tools - this returns a ListToolsResult object
            tools_result = await self.session.list_tools()
            
            # Extract tools from result - tools should be in .tools attribute
            if hasattr(tools_result, 'tools'):
                tools_list = tools_result.tools
            else:
                # Fallback in case the structure is different
                tools_list = tools_result
            
            required_tools = {'get_pokemon', 'battle_simulate', 'get_type_effectiveness'}
            available_tools = {t.name for t in tools_list}
            
            if not required_tools.issubset(available_tools):
                missing = required_tools - available_tools
                raise ValueError(f"Missing required tools: {missing}")

            logger.info(f"📋 Available tools: {available_tools}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to start MCP connection: {e}")
            await self.stop()
            return False
    
    async def stop(self):
        """Clean up MCP connection"""
        try:
            await self.exit_stack.aclose()
        except Exception as e:
            logger.error(f"Error stopping MCP connection: {e}")
    
    def _create_system_prompt(self) -> str:
        """Create system prompt for Groq"""
        return """You are a Pokémon expert assistant with access to real Pokémon data and battle simulation capabilities through MCP tools.

You have access to these tools:
1. get_pokemon - Get detailed information about any Pokémon (stats, types, abilities, moves)
2. battle_simulate - Simulate realistic battles between two Pokémon with full combat mechanics
3. get_type_effectiveness - Calculate type effectiveness for strategic analysis

When users ask about Pokémon:
- Use get_pokemon for data queries about specific Pokémon
- Use battle_simulate for battle scenarios or "who would win" questions
- Use get_type_effectiveness for type matchup questions
- Always use the real data from tools rather than your training knowledge
- Provide engaging, detailed responses with strategic insights
- Format your responses nicely with clear sections

Be enthusiastic about Pokémon and provide helpful battle strategy advice!"""
    
    async def _call_tool_safely(self, name: str, arguments: dict) -> MCPToolResult:
        """Wrapper for safe tool execution - FIXED VERSION"""
        try:
            logger.info(f"🛠️ Calling tool: {name} with args: {arguments}")
            result = await self.session.call_tool(name, arguments)
            
            # Handle different result types safely
            result_info = f"type: {type(result).__name__}"
            if hasattr(result, '__len__'):
                try:
                    result_info += f", length: {len(result)}"
                except:
                    result_info += ", length: unknown"
            
            logger.info(f"📥 Tool result {result_info}")
            
            # Handle CallToolResult object
            if hasattr(result, 'content') and result.content:
                # This is likely a CallToolResult with a content attribute
                content_list = result.content
                if content_list and len(content_list) > 0:
                    content = content_list[0]
                    logger.info(f"📄 Content type: {type(content).__name__}, has text: {hasattr(content, 'text')}")
                    
                    if hasattr(content, 'text'):
                        text_content = content.text
                        logger.info(f"✅ Got text content, length: {len(text_content)}")
                        return MCPToolResult(success=True, data=text_content)
                    else:
                        logger.error(f"❌ Content object doesn't have text attribute")
                        return MCPToolResult(success=False, data="", error=f"Tool '{name}' returned content without text attribute.")
                else:
                    logger.error(f"❌ CallToolResult has empty content")
                    return MCPToolResult(success=False, data="", error=f"Tool '{name}' returned empty content.")
            
            # Handle direct list result
            elif isinstance(result, list) and len(result) > 0:
                content = result[0]
                logger.info(f"📄 Content type: {type(content).__name__}, has text: {hasattr(content, 'text')}")
                
                if hasattr(content, 'text'):
                    text_content = content.text
                    logger.info(f"✅ Got text content, length: {len(text_content)}")
                    return MCPToolResult(success=True, data=text_content)
                else:
                    logger.error(f"❌ Content object doesn't have text attribute")
                    return MCPToolResult(success=False, data="", error=f"Tool '{name}' returned content without text attribute.")
            
            else:
                logger.error(f"❌ Unexpected result structure: {result}")
                return MCPToolResult(success=False, data="", error=f"Tool '{name}' returned unexpected result structure.")
                
        except Exception as e:
            logger.error(f"💥 Error calling tool {name}: {e}")
            return MCPToolResult(success=False, data="", error=str(e))
    
    async def _determine_and_use_tools(self, user_message: str) -> List[MCPToolResult]:
        """Determine what tools to use based on user message and execute them"""
        user_lower = user_message.lower()
        results = []
        
        logger.info(f"🔍 Analyzing message: {user_message}")
        
        # Battle simulation intent
        if any(word in user_lower for word in ["battle", "fight", "vs", "versus", "simulate", "who would win", "winner"]):
            logger.info("🥊 Detected battle intent")
            words = user_message.replace(",", " ").replace("vs", " ").replace("versus", " ").split()
            pokemon_names = []
            
            skip_words = {"and", "vs", "versus", "battle", "simulate", "between", "fight", "who", "would", "win", "winner", "the", "a", "an"}
            for word in words:
                clean_word = word.strip(".,!?()").lower()
                if len(clean_word) > 2 and clean_word not in skip_words:
                    pokemon_names.append(clean_word)
            
            logger.info(f"🎯 Found potential pokemon names: {pokemon_names}")
            
            if len(pokemon_names) >= 2:
                result = await self._call_tool_safely("battle_simulate", {
                    "pokemon1": pokemon_names[0], 
                    "pokemon2": pokemon_names[1]
                })
                results.append(result)
        
        # Pokémon data intent
        elif any(word in user_lower for word in ["stats", "info", "about", "data", "moves", "abilities", "what is", "tell me about", "show me"]):
            logger.info("📊 Detected pokemon data intent")
            words = user_message.split()
            skip_words = {"what", "are", "is", "the", "stats", "info", "about", "data", "moves", "abilities", "tell", "me", "show", "get", "list", "that", "can", "learn"}
            
            for word in words:
                clean_word = word.strip(".,!?()").lower()
                if len(clean_word) > 2 and clean_word not in skip_words:
                    logger.info(f"🔍 Trying to get pokemon: {clean_word}")
                    result = await self._call_tool_safely("get_pokemon", {"name": clean_word})
                    if result.success:
                        results.append(result)
                        break
        
        # Type effectiveness intent
        elif any(word in user_lower for word in ["effective", "weakness", "resist", "type", "super effective", "not very effective"]):
            logger.info("⚡ Detected type effectiveness intent")
            words = user_message.split()
            skip_words = {"what", "is", "are", "the", "type", "weakness", "weak", "resist", "super", "effective", "against", "not", "very", "double"}
            
            types_found = []
            for word in words:
                clean_word = word.strip(".,!?()").lower()
                if len(clean_word) > 2 and clean_word not in skip_words:
                    types_found.append(clean_word)
            
            logger.info(f"🔥 Found potential types: {types_found}")
            
            if len(types_found) >= 1:
                # Try first as attacking type, second (if available) as defending type
                attacking_type = types_found[0]
                defending_types = types_found[1:2] if len(types_found) > 1 else [types_found[0]]
                
                result = await self._call_tool_safely("get_type_effectiveness", {
                    "attacking_type": attacking_type, 
                    "defending_types": defending_types
                })
                if result.success:
                    results.append(result)
        
        logger.info(f"📝 Found {len(results)} tool results")
        return results
    
    async def chat(self, user_message: str) -> str:
        """Process user message and return AI response"""
        try:
            logger.info(f"💬 Processing user message: {user_message}")
            mcp_results = await self._determine_and_use_tools(user_message)
            
            context_parts = []
            if mcp_results:
                context_parts.append("Real-time data from Pokémon MCP server:")
                for i, result in enumerate(mcp_results):
                    if result.success:
                        context_parts.append(f"\nTool Result {i+1}:\n{result.data}")
                        logger.info(f"✅ Tool result {i+1}: Success, data length: {len(result.data)}")
                    else:
                        context_parts.append(f"\nTool Error {i+1}: {result.error}")
                        logger.error(f"❌ Tool result {i+1}: Error: {result.error}")
            else:
                logger.info("ℹ️ No MCP tools used")
            
            context = "\n".join(context_parts) if context_parts else ""
            
            messages = [
                {"role": "system", "content": self._create_system_prompt()},
            ]
            
            # Keep last 8 messages for context
            messages.extend(self.conversation_history[-8:])
            
            user_content = user_message
            if context:
                user_content += f"\n\nMCP Tool Data:\n{context}"
                logger.info(f"📎 Added context to message, total length: {len(user_content)}")
            
            messages.append({"role": "user", "content": user_content})
            
            logger.info("🤖 Calling Groq API...")
            response = self.groq_client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=messages,
                temperature=0.7,
                max_tokens=2000,
            )
            
            assistant_response = response.choices[0].message.content
            logger.info(f"✅ Got Groq response, length: {len(assistant_response)}")
            
            self.conversation_history.append({"role": "user", "content": user_message})
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            
            return assistant_response
            
        except Exception as e:
            logger.error(f"💥 Error in chat: {e}")
            return f"Sorry, I encountered an error: {str(e)}"

async def main():
    """Main function to run the Groq Pokemon client"""
    
    GROQ_API_KEY = os.getenv("GROQ_API_KEY")
    if not GROQ_API_KEY:
        print("❌ Error: GROQ_API_KEY environment variable not set!")
        print("   Set it with: export GROQ_API_KEY='your_api_key_here'")
        print("   Get your API key from: https://console.groq.com/keys")
        return
    
    MCP_SERVER_PATH = "pokemon_mcp_server.py"
    if not os.path.exists(MCP_SERVER_PATH):
        print(f"❌ Error: MCP server file not found: {MCP_SERVER_PATH}")
        print("   Make sure pokemon_mcp_server.py is in the current directory")
        return
    
    print("🎮 Starting Pokémon AI Assistant with Groq + MCP...")
    print("=" * 60)
    
    assistant = GroqPokemonAssistant(GROQ_API_KEY, MCP_SERVER_PATH)
    
    try:
        if not await assistant.start():
            print("❌ Failed to start assistant")
            return
        
        print("✅ Assistant ready!")
        print("\n💡 Try these example queries:")
        print("   • 'Tell me about Charizard'")
        print("   • 'Simulate a battle between Pikachu and Blastoise'")
        print("   • 'What types are effective against Dragon?'")
        print("   • 'Show me Mewtwo's stats'")
        print("=" * 60)
        
        while True:
            try:
                user_input = input("\n🧑 You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'bye', 'stop']:
                    print("👋 Thanks for using the Pokémon Assistant! Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                print("🤖 Assistant: ", end="", flush=True)
                response = await assistant.chat(user_input)
                print(response)
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
    
    except Exception as e:
        print(f"❌ Failed to start assistant: {e}")
    
    finally:
        await assistant.stop()
        print("🔄 Connection closed.")

if __name__ == "__main__":
    asyncio.run(main())