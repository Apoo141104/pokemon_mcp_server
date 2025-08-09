#!/usr/bin/env python3
"""
Pokémon Battle Simulation MCP Server
A Model Context Protocol server using the official MCP library that provides Pokémon data resources and battle simulation tools.
"""

import asyncio
import json
import logging
import random
import math
from typing import Any, Dict, List, Optional, Tuple, Sequence
from dataclasses import dataclass, asdict
from enum import Enum

import httpx
from mcp.server import Server
from mcp import types

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pokemon-mcp-server")

# Type definitions
@dataclass
class PokemonStats:
    hp: int
    attack: int
    defense: int
    special_attack: int
    special_defense: int
    speed: int

@dataclass
class Move:
    name: str
    type: str
    category: str  # physical, special, status
    power: Optional[int]
    accuracy: int
    pp: int
    priority: int = 0
    effect: Optional[str] = None

@dataclass
class Pokemon:
    id: int
    name: str
    types: List[str]
    stats: PokemonStats
    abilities: List[str]
    moves: List[Move]
    height: int
    weight: int
    sprite_url: Optional[str] = None

class StatusEffect(Enum):
    NONE = "none"
    BURN = "burn"
    POISON = "poison"
    PARALYSIS = "paralysis"
    SLEEP = "sleep"
    FREEZE = "freeze"

@dataclass
class BattlePokemon:
    pokemon: Pokemon
    current_hp: int
    status: StatusEffect = StatusEffect.NONE
    status_turns: int = 0
    
    def __post_init__(self):
        if self.current_hp == 0:
            self.current_hp = self.pokemon.stats.hp

class PokemonDataManager:
    """Manages Pokémon data fetching and caching"""
    
    def __init__(self):
        self.cache: Dict[str, Pokemon] = {}
        self.type_chart = self._initialize_type_chart()
        
    def _initialize_type_chart(self) -> Dict[str, Dict[str, float]]:
        """Initialize comprehensive type effectiveness chart"""
        return {
            "normal": {"rock": 0.5, "ghost": 0.0, "steel": 0.5},
            "fire": {"fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 2.0, "bug": 2.0, "rock": 0.5, "dragon": 0.5, "steel": 2.0},
            "water": {"fire": 2.0, "water": 0.5, "grass": 0.5, "ground": 2.0, "rock": 2.0, "dragon": 0.5},
            "grass": {"fire": 0.5, "water": 2.0, "grass": 0.5, "poison": 0.5, "ground": 2.0, "flying": 0.5, "bug": 0.5, "rock": 2.0, "dragon": 0.5, "steel": 0.5},
            "electric": {"water": 2.0, "grass": 0.5, "ground": 0.0, "flying": 2.0, "dragon": 0.5, "electric": 0.5},
            "ice": {"fire": 0.5, "water": 0.5, "grass": 2.0, "ice": 0.5, "ground": 2.0, "flying": 2.0, "dragon": 2.0, "steel": 0.5},
            "fighting": {"normal": 2.0, "ice": 2.0, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "rock": 2.0, "ghost": 0.0, "dark": 2.0, "steel": 2.0, "fairy": 0.5},
            "poison": {"grass": 2.0, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0.0, "fairy": 2.0},
            "ground": {"fire": 2.0, "electric": 2.0, "grass": 0.5, "poison": 2.0, "flying": 0.0, "bug": 0.5, "rock": 2.0, "steel": 2.0},
            "flying": {"electric": 0.5, "grass": 2.0, "ice": 0.5, "fighting": 2.0, "bug": 2.0, "rock": 0.5, "steel": 0.5},
            "psychic": {"fighting": 2.0, "poison": 2.0, "psychic": 0.5, "dark": 0.0, "steel": 0.5},
            "bug": {"fire": 0.5, "grass": 2.0, "fighting": 0.5, "poison": 0.5, "flying": 0.5, "psychic": 2.0, "ghost": 0.5, "dark": 2.0, "steel": 0.5, "fairy": 0.5},
            "rock": {"fire": 2.0, "ice": 2.0, "fighting": 0.5, "ground": 0.5, "flying": 2.0, "bug": 2.0, "steel": 0.5},
            "ghost": {"normal": 0.0, "psychic": 2.0, "ghost": 2.0, "dark": 0.5},
            "dragon": {"dragon": 2.0, "steel": 0.5, "fairy": 0.0},
            "dark": {"fighting": 0.5, "psychic": 2.0, "ghost": 2.0, "dark": 0.5, "fairy": 0.5},
            "steel": {"fire": 0.5, "water": 0.5, "electric": 0.5, "ice": 2.0, "rock": 2.0, "steel": 0.5, "fairy": 2.0},
            "fairy": {"fire": 0.5, "fighting": 2.0, "poison": 0.5, "dragon": 2.0, "dark": 2.0, "steel": 0.5}
        }
    
    async def get_pokemon(self, identifier: str) -> Optional[Pokemon]:
        """Fetch Pokémon data by name or ID"""
        identifier = identifier.lower().replace(" ", "-")
        
        if identifier in self.cache:
            return self.cache[identifier]
        
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                # Fetch basic Pokémon data
                response = await client.get(f"https://pokeapi.co/api/v2/pokemon/{identifier}")
                if response.status_code != 200:
                    logger.error(f"Failed to fetch Pokémon {identifier}: {response.status_code}")
                    return None
                
                data = response.json()
                
                # Parse stats
                stats = PokemonStats(
                    hp=next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "hp"),
                    attack=next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "attack"),
                    defense=next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "defense"),
                    special_attack=next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "special-attack"),
                    special_defense=next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "special-defense"),
                    speed=next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "speed")
                )
                
                # Parse types
                types_list = [t["type"]["name"] for t in data["types"]]
                
                # Parse abilities
                abilities = [a["ability"]["name"] for a in data["abilities"]]
                
                # Fetch some moves
                moves = []
                move_urls = [move_data["move"]["url"] for move_data in data["moves"][:15]]
                
                for move_url in move_urls:
                    try:
                        move_response = await client.get(move_url)
                        if move_response.status_code == 200:
                            move_info = move_response.json()
                            move = Move(
                                name=move_info["name"],
                                type=move_info["type"]["name"],
                                category=move_info["damage_class"]["name"] if move_info["damage_class"] else "status",
                                power=move_info["power"],
                                accuracy=move_info["accuracy"] or 100,
                                pp=move_info["pp"],
                                priority=move_info["priority"],
                                effect=move_info["effect_entries"][0]["short_effect"] if move_info["effect_entries"] else None
                            )
                            moves.append(move)
                    except Exception as e:
                        logger.warning(f"Failed to fetch move data: {e}")
                        continue
                
                # Create Pokémon object
                pokemon = Pokemon(
                    id=data["id"],
                    name=data["name"],
                    types=types_list,
                    stats=stats,
                    abilities=abilities,
                    moves=moves,
                    height=data["height"],
                    weight=data["weight"],
                    sprite_url=data["sprites"]["front_default"]
                )
                
                self.cache[identifier] = pokemon
                self.cache[str(data["id"])] = pokemon
                self.cache[data["name"].lower()] = pokemon
                
                return pokemon
                
        except Exception as e:
            logger.error(f"Error fetching Pokémon {identifier}: {e}")
            return None
    
    def get_type_effectiveness(self, attacking_type: str, defending_types: List[str]) -> float:
        """Calculate type effectiveness multiplier"""
        multiplier = 1.0
        
        for defending_type in defending_types:
            if attacking_type in self.type_chart and defending_type in self.type_chart[attacking_type]:
                multiplier *= self.type_chart[attacking_type][defending_type]
        
        return multiplier

class BattleSimulator:
    """Handles Pokémon battle simulation - IMPROVED VERSION"""
    
    def __init__(self, data_manager: PokemonDataManager):
        self.data_manager = data_manager
        
    def calculate_damage(self, attacker: BattlePokemon, defender: BattlePokemon, move: Move) -> int:
        """Calculate damage dealt by a move using accurate Pokémon damage formula"""
        if move.power is None:
            return 0
        
        # Base damage calculation using official Pokémon damage formula
        level = 50  # Standard competitive level
        
        # Determine attack and defense stats based on move category
        if move.category == "physical":
            attack_stat = attacker.pokemon.stats.attack
            defense_stat = defender.pokemon.stats.defense
        elif move.category == "special":
            attack_stat = attacker.pokemon.stats.special_attack
            defense_stat = defender.pokemon.stats.special_defense
        else:  # status moves
            return 0
        
        # Apply burn effect to physical moves (halves attack)
        if attacker.status == StatusEffect.BURN and move.category == "physical":
            attack_stat = attack_stat // 2
        
        # Base damage formula: ((((2*Level + 10)/250) * (Attack/Defense) * Power) + 2)
        base_damage = ((((2 * level + 10) / 250) * (attack_stat / defense_stat) * move.power) + 2)
        
        # Apply type effectiveness
        type_multiplier = self.data_manager.get_type_effectiveness(move.type, defender.pokemon.types)
        base_damage *= type_multiplier
        
        # Apply STAB (Same Type Attack Bonus) - 1.5x if move type matches attacker's type
        if move.type in attacker.pokemon.types:
            base_damage *= 1.5
        
        # Apply random factor (85-100%)
        base_damage *= random.uniform(0.85, 1.0)
        
        # Ensure minimum damage of 1
        return max(1, int(base_damage))
    
    def apply_status_effect(self, pokemon: BattlePokemon, status: StatusEffect) -> str:
        """Apply status effect to Pokémon"""
        if pokemon.status != StatusEffect.NONE:
            return f"{pokemon.pokemon.name.title()} is already affected by {pokemon.status.value}!"
        
        pokemon.status = status
        pokemon.status_turns = 0
        
        status_messages = {
            StatusEffect.BURN: "was burned!",
            StatusEffect.POISON: "was poisoned!",
            StatusEffect.PARALYSIS: "was paralyzed!",
            StatusEffect.SLEEP: "fell asleep!",
            StatusEffect.FREEZE: "was frozen solid!"
        }
        
        return f"{pokemon.pokemon.name.title()} {status_messages.get(status, 'was affected!')}"
    
    def process_status_effects(self, pokemon: BattlePokemon) -> List[str]:
        """Process status effects at end of turn"""
        messages = []
        
        if pokemon.status == StatusEffect.BURN:
            damage = max(1, pokemon.pokemon.stats.hp // 16)
            pokemon.current_hp = max(0, pokemon.current_hp - damage)
            messages.append(f"💥 {pokemon.pokemon.name.title()} is hurt by its burn! (-{damage} HP)")
            
        elif pokemon.status == StatusEffect.POISON:
            damage = max(1, pokemon.pokemon.stats.hp // 8)
            pokemon.current_hp = max(0, pokemon.current_hp - damage)
            messages.append(f"☠️ {pokemon.pokemon.name.title()} is hurt by poison! (-{damage} HP)")
        
        elif pokemon.status == StatusEffect.SLEEP:
            pokemon.status_turns += 1
            if pokemon.status_turns >= random.randint(1, 3):  # Wake up after 1-3 turns
                pokemon.status = StatusEffect.NONE
                pokemon.status_turns = 0
                messages.append(f"😴 {pokemon.pokemon.name.title()} woke up!")
        
        elif pokemon.status == StatusEffect.FREEZE:
            if random.random() < 0.2:  # 20% chance to thaw
                pokemon.status = StatusEffect.NONE
                pokemon.status_turns = 0
                messages.append(f"🧊 {pokemon.pokemon.name.title()} thawed out!")
        
        return messages
    
    def select_move(self, pokemon: BattlePokemon, opponent: BattlePokemon) -> Optional[Move]:
        """Intelligently select a move for battle"""
        available_moves = [move for move in pokemon.pokemon.moves if move.power and move.power > 0]
        
        if not available_moves:
            return None
        
        # Simple AI: prefer moves that are super effective
        best_moves = []
        best_effectiveness = 0
        
        for move in available_moves:
            effectiveness = self.data_manager.get_type_effectiveness(move.type, opponent.pokemon.types)
            if effectiveness > best_effectiveness:
                best_effectiveness = effectiveness
                best_moves = [move]
            elif effectiveness == best_effectiveness:
                best_moves.append(move)
        
        # Among equally effective moves, prefer higher power
        if len(best_moves) > 1:
            best_moves.sort(key=lambda m: m.power or 0, reverse=True)
        
        return best_moves[0] if best_moves else random.choice(available_moves)
    
    async def battle_simulate(self, pokemon1_name: str, pokemon2_name: str) -> Dict[str, Any]:
        """Enhanced battle simulation with detailed structured output"""
        logger.info(f"Starting enhanced battle simulation between {pokemon1_name} and {pokemon2_name}")
        
        # Fetch Pokémon data
        pokemon1_data = await self.data_manager.get_pokemon(pokemon1_name)
        pokemon2_data = await self.data_manager.get_pokemon(pokemon2_name)
        
        if not pokemon1_data:
            logger.error(f"Could not find Pokémon: {pokemon1_name}")
            return {"error": f"Could not find Pokémon: {pokemon1_name}"}
        if not pokemon2_data:
            logger.error(f"Could not find Pokémon: {pokemon2_name}")
            return {"error": f"Could not find Pokémon: {pokemon2_name}"}
        
        logger.info(f"Found both Pokémon: {pokemon1_data.name} and {pokemon2_data.name}")
        
        # Initialize battle Pokémon
        battle_pokemon1 = BattlePokemon(pokemon1_data, pokemon1_data.stats.hp)
        battle_pokemon2 = BattlePokemon(pokemon2_data, pokemon2_data.stats.hp)
        
        # Create detailed battle introduction
        battle_log = []
        battle_log.append("=" * 80)
        battle_log.append("🎮 **POKÉMON BATTLE ARENA**")
        battle_log.append("=" * 80)
        battle_log.append("")
        
        # Detailed Pokemon information
        battle_log.append("### 📋 **Battle Participants**")
        battle_log.append("")
        
        # Pokemon 1 details
        battle_log.append(f"**🔵 {pokemon1_data.name.title()}** (#{pokemon1_data.id:03d})")
        battle_log.append(f"   🏷️ **Type:** {' / '.join([t.title() for t in pokemon1_data.types])}")
        battle_log.append(f"   📊 **Base Stats:**")
        battle_log.append(f"     ❤️  HP: {pokemon1_data.stats.hp}")
        battle_log.append(f"     ⚔️  Attack: {pokemon1_data.stats.attack}")
        battle_log.append(f"     🛡️  Defense: {pokemon1_data.stats.defense}")
        battle_log.append(f"     🔮 Sp. Attack: {pokemon1_data.stats.special_attack}")
        battle_log.append(f"     🛡️ Sp. Defense: {pokemon1_data.stats.special_defense}")
        battle_log.append(f"     💨 Speed: {pokemon1_data.stats.speed}")
        total1 = (pokemon1_data.stats.hp + pokemon1_data.stats.attack + pokemon1_data.stats.defense + 
                  pokemon1_data.stats.special_attack + pokemon1_data.stats.special_defense + pokemon1_data.stats.speed)
        battle_log.append(f"     📈 **Total: {total1}**")
        battle_log.append(f"   ⚡ **Abilities:** {', '.join([a.replace('-', ' ').title() for a in pokemon1_data.abilities])}")
        
        if pokemon1_data.moves:
            battle_log.append(f"   🥊 **Available Moves:**")
            for move in pokemon1_data.moves[:6]:  # Show first 6 moves
                power_text = f" ({move.power} power)" if move.power else " (Status)"
                battle_log.append(f"     • {move.name.replace('-', ' ').title()} - {move.type.title()}{power_text}")
        battle_log.append("")
        
        # Pokemon 2 details  
        battle_log.append(f"**🔴 {pokemon2_data.name.title()}** (#{pokemon2_data.id:03d})")
        battle_log.append(f"   🏷️ **Type:** {' / '.join([t.title() for t in pokemon2_data.types])}")
        battle_log.append(f"   📊 **Base Stats:**")
        battle_log.append(f"     ❤️  HP: {pokemon2_data.stats.hp}")
        battle_log.append(f"     ⚔️  Attack: {pokemon2_data.stats.attack}")
        battle_log.append(f"     🛡️  Defense: {pokemon2_data.stats.defense}")
        battle_log.append(f"     🔮 Sp. Attack: {pokemon2_data.stats.special_attack}")
        battle_log.append(f"     🛡️ Sp. Defense: {pokemon2_data.stats.special_defense}")
        battle_log.append(f"     💨 Speed: {pokemon2_data.stats.speed}")
        total2 = (pokemon2_data.stats.hp + pokemon2_data.stats.attack + pokemon2_data.stats.defense + 
                  pokemon2_data.stats.special_attack + pokemon2_data.stats.special_defense + pokemon2_data.stats.speed)
        battle_log.append(f"     📈 **Total: {total2}**")
        battle_log.append(f"   ⚡ **Abilities:** {', '.join([a.replace('-', ' ').title() for a in pokemon2_data.abilities])}")
        
        if pokemon2_data.moves:
            battle_log.append(f"   🥊 **Available Moves:**")
            for move in pokemon2_data.moves[:6]:  # Show first 6 moves
                power_text = f" ({move.power} power)" if move.power else " (Status)"
                battle_log.append(f"     • {move.name.replace('-', ' ').title()} - {move.type.title()}{power_text}")
        battle_log.append("")
        
        # Battle conditions
        battle_log.append("### ⚔️ **Battle Conditions**")
        battle_log.append(f"🎯 **Battle Level:** 50 (Standard)")
        battle_log.append(f"🏟️ **Arena:** Standard Battle Arena")
        battle_log.append(f"📏 **Max Turns:** 50")
        battle_log.append("")
        
        # Speed comparison and first move prediction
        speed1 = pokemon1_data.stats.speed
        speed2 = pokemon2_data.stats.speed
        if speed1 > speed2:
            battle_log.append(f"⚡ **Speed Advantage:** {pokemon1_data.name.title()} ({speed1}) goes first!")
        elif speed2 > speed1:
            battle_log.append(f"⚡ **Speed Advantage:** {pokemon2_data.name.title()} ({speed2}) goes first!")
        else:
            battle_log.append(f"⚡ **Speed Tie:** Both Pokémon have equal speed ({speed1})!")
        battle_log.append("")
        
        battle_log.append("=" * 80)
        battle_log.append("🥊 **BATTLE BEGINS!**")
        battle_log.append("=" * 80)
        
        turn = 0
        max_turns = 50
        detailed_turns = []
        
        while battle_pokemon1.current_hp > 0 and battle_pokemon2.current_hp > 0 and turn < max_turns:
            turn += 1
            turn_log = []
            turn_log.append(f"\n### 🔥 **Turn {turn}**")
            turn_log.append("-" * 40)
            
            # Show current HP status
            hp1_percent = int((battle_pokemon1.current_hp / pokemon1_data.stats.hp) * 100)
            hp2_percent = int((battle_pokemon2.current_hp / pokemon2_data.stats.hp) * 100)
            
            turn_log.append(f"💖 **HP Status:**")
            turn_log.append(f"   🔵 {pokemon1_data.name.title()}: {battle_pokemon1.current_hp}/{pokemon1_data.stats.hp} HP ({hp1_percent}%)")
            turn_log.append(f"   🔴 {pokemon2_data.name.title()}: {battle_pokemon2.current_hp}/{pokemon2_data.stats.hp} HP ({hp2_percent}%)")
            turn_log.append("")
            
            # Determine turn order
            first_pokemon, second_pokemon = self._determine_turn_order(battle_pokemon1, battle_pokemon2)
            
            # First Pokémon's turn
            if first_pokemon.current_hp > 0:
                turn_log.append(f"🎯 **{first_pokemon.pokemon.name.title()}'s Turn:**")
                messages = await self._execute_detailed_turn(first_pokemon, second_pokemon, turn_log)
                turn_log.extend(messages)
                
                if second_pokemon.current_hp <= 0:
                    turn_log.append(f"💀 **{second_pokemon.pokemon.name.title()} has fainted!**")
                    break
            
            turn_log.append("")
            
            # Second Pokémon's turn
            if second_pokemon.current_hp > 0:
                turn_log.append(f"🎯 **{second_pokemon.pokemon.name.title()}'s Turn:**")
                messages = await self._execute_detailed_turn(second_pokemon, first_pokemon, turn_log)
                turn_log.extend(messages)
                
                if first_pokemon.current_hp <= 0:
                    turn_log.append(f"💀 **{first_pokemon.pokemon.name.title()} has fainted!**")
                    break
            
            # Process status effects
            turn_log.append("")
            turn_log.append("🌟 **End of Turn Effects:**")
            for pokemon in [battle_pokemon1, battle_pokemon2]:
                if pokemon.current_hp > 0:
                    status_messages = self.process_status_effects(pokemon)
                    if status_messages:
                        turn_log.extend([f"   {msg}" for msg in status_messages])
                    else:
                        turn_log.append(f"   ✅ {pokemon.pokemon.name.title()}: No status effects")
                        
                    if pokemon.current_hp <= 0:
                        turn_log.append(f"   💀 **{pokemon.pokemon.name.title()} fainted from status effects!**")
                        break
            
            detailed_turns.append(turn_log)
            battle_log.extend(turn_log)
        
        # Battle conclusion
        battle_log.append("\n" + "=" * 80)
        battle_log.append("🏆 **BATTLE CONCLUSION**")
        battle_log.append("=" * 80)
        
        # Determine winner
        if battle_pokemon1.current_hp > 0 and battle_pokemon2.current_hp <= 0:
            winner = pokemon1_data.name.title()
            winner_hp = battle_pokemon1.current_hp
            winner_max_hp = pokemon1_data.stats.hp
            loser = pokemon2_data.name.title()
        elif battle_pokemon2.current_hp > 0 and battle_pokemon1.current_hp <= 0:
            winner = pokemon2_data.name.title()
            winner_hp = battle_pokemon2.current_hp
            winner_max_hp = pokemon2_data.stats.hp
            loser = pokemon1_data.name.title()
        else:
            winner = "Draw (Time Limit Reached)"
            winner_hp = 0
            winner_max_hp = 0
            loser = "No one"
        
        battle_log.append(f"🎉 **WINNER: {winner}!**")
        
        if winner != "Draw (Time Limit Reached)":
            hp_percentage = int((winner_hp / winner_max_hp) * 100)
            battle_log.append(f"💪 **Final Status:** {winner} wins with {winner_hp}/{winner_max_hp} HP ({hp_percentage}%)")
            battle_log.append(f"😵 **Defeated:** {loser}")
        
        battle_log.append(f"⏱️ **Battle Duration:** {turn} turns")
        battle_log.append("")
        
        # Battle statistics
        battle_log.append("### 📊 **Battle Statistics**")
        battle_log.append(f"🔥 **Total Turns:** {turn}")
        battle_log.append(f"⚡ **Faster Pokémon:** {pokemon1_data.name.title() if speed1 >= speed2 else pokemon2_data.name.title()}")
        battle_log.append(f"💪 **Higher Attack:** {pokemon1_data.name.title() if pokemon1_data.stats.attack >= pokemon2_data.stats.attack else pokemon2_data.name.title()}")
        battle_log.append(f"🛡️ **Higher Defense:** {pokemon1_data.name.title() if pokemon1_data.stats.defense >= pokemon2_data.stats.defense else pokemon2_data.name.title()}")
        battle_log.append("")
        
        # Strategic analysis
        battle_log.append("### 🧠 **Strategic Analysis**")
        if winner != "Draw (Time Limit Reached)":
            winner_data = pokemon1_data if winner == pokemon1_data.name.title() else pokemon2_data
            loser_data = pokemon2_data if winner == pokemon1_data.name.title() else pokemon1_data
            
            # Analyze why the winner won
            if winner_data.stats.speed > loser_data.stats.speed:
                battle_log.append(f"⚡ **Speed Advantage:** {winner}'s superior speed ({winner_data.stats.speed} vs {loser_data.stats.speed}) allowed it to strike first consistently.")
            
            if winner_data.stats.attack > loser_data.stats.defense or winner_data.stats.special_attack > loser_data.stats.special_defense:
                battle_log.append(f"💥 **Offensive Power:** {winner}'s strong attacks overwhelmed {loser}'s defenses.")
            
            battle_log.append(f"🎯 **Key Factor:** Type advantages, move selection, and stat distribution all contributed to {winner}'s victory.")
        
        battle_log.append("=" * 80)
        
        logger.info(f"Enhanced battle completed. Winner: {winner}")
        
        return {
            "pokemon1": {
                "name": pokemon1_data.name.title(),
                "types": pokemon1_data.types,
                "final_hp": battle_pokemon1.current_hp,
                "max_hp": pokemon1_data.stats.hp,
                "status": battle_pokemon1.status.value,
                "stats": asdict(pokemon1_data.stats),
                "abilities": pokemon1_data.abilities
            },
            "pokemon2": {
                "name": pokemon2_data.name.title(),
                "types": pokemon2_data.types,
                "final_hp": battle_pokemon2.current_hp,
                "max_hp": pokemon2_data.stats.hp,
                "status": battle_pokemon2.status.value,
                "stats": asdict(pokemon2_data.stats),
                "abilities": pokemon2_data.abilities
            },
            "winner": winner,
            "turns": turn,
            "battle_log": battle_log,
            "detailed_turns": detailed_turns
        }

    def _determine_turn_order(self, pokemon1: BattlePokemon, pokemon2: BattlePokemon) -> Tuple[BattlePokemon, BattlePokemon]:
        """Determine which Pokémon goes first based on speed"""
        speed1 = pokemon1.pokemon.stats.speed
        speed2 = pokemon2.pokemon.stats.speed
        
        # Paralysis reduces speed by 75%
        if pokemon1.status == StatusEffect.PARALYSIS:
            speed1 = speed1 // 4
        if pokemon2.status == StatusEffect.PARALYSIS:
            speed2 = speed2 // 4
        
        if speed1 >= speed2:
            return pokemon1, pokemon2
        else:
            return pokemon2, pokemon1
    
    async def _execute_detailed_turn(self, attacker: BattlePokemon, defender: BattlePokemon, turn_log: List[str]) -> List[str]:
        """Execute a detailed turn with comprehensive information"""
        messages = []
        
        # Check if Pokémon can move (status conditions)
        if attacker.status == StatusEffect.PARALYSIS and random.random() < 0.25:
            messages.append(f"   ⚡ {attacker.pokemon.name.title()} is paralyzed and cannot move!")
            return messages
        
        if attacker.status == StatusEffect.SLEEP:
            messages.append(f"   😴 {attacker.pokemon.name.title()} is fast asleep and cannot move!")
            return messages
            
        if attacker.status == StatusEffect.FREEZE:
            messages.append(f"   🧊 {attacker.pokemon.name.title()} is frozen solid and cannot move!")
            return messages
        
        # Select a move
        move = self.select_move(attacker, defender)
        if not move:
            messages.append(f"   ❌ {attacker.pokemon.name.title()} has no usable moves!")
            return messages
        
        # Show move selection
        move_name = move.name.replace('-', ' ').title()
        messages.append(f"   🎯 **Move Selected:** {move_name}")
        messages.append(f"   🏷️ **Move Type:** {move.type.title()} ({move.category.title()})")
        if move.power:
            messages.append(f"   💪 **Base Power:** {move.power}")
        messages.append(f"   🎯 **Accuracy:** {move.accuracy}%")
        messages.append("")
        
        # Check accuracy
        accuracy_roll = random.randint(1, 100)
        if accuracy_roll > move.accuracy:
            messages.append(f"   🎲 **Accuracy Roll:** {accuracy_roll}/{move.accuracy} - **MISSED!**")
            messages.append(f"   ❌ {attacker.pokemon.name.title()} used {move_name} but it missed!")
            return messages
        
        messages.append(f"   🎲 **Accuracy Roll:** {accuracy_roll}/{move.accuracy} - **HIT!**")
        messages.append(f"   ⚡ **{attacker.pokemon.name.title()} used {move_name}!**")
        messages.append("")
        
        # Calculate damage with detailed breakdown
        if move.power:
            damage = self.calculate_damage(attacker, defender, move)
            type_mult = self.data_manager.get_type_effectiveness(move.type, defender.pokemon.types)
            
            # Show damage calculation details
            messages.append(f"   🧮 **Damage Calculation:**")
            messages.append(f"     📊 Base Power: {move.power}")
            
            if move.category == "physical":
                messages.append(f"     ⚔️ Attack Stat: {attacker.pokemon.stats.attack}")
                messages.append(f"     🛡️ Defense Stat: {defender.pokemon.stats.defense}")
            else:
                messages.append(f"     🔮 Sp. Attack Stat: {attacker.pokemon.stats.special_attack}")
                messages.append(f"     🛡️ Sp. Defense Stat: {defender.pokemon.stats.special_defense}")
            
            messages.append(f"     🎯 Type Effectiveness: {type_mult}x")
            
            # STAB check
            if move.type in attacker.pokemon.types:
                messages.append(f"     ⭐ STAB (Same Type Attack Bonus): 1.5x")
            
            messages.append(f"     💥 **Final Damage: {damage}**")
            messages.append("")
            
            # Apply damage
            old_hp = defender.current_hp
            defender.current_hp = max(0, defender.current_hp - damage)
            
            # Type effectiveness messages with more detail
            if type_mult > 1:
                messages.append(f"   🔥 **It's super effective!** ({type_mult}x damage)")
            elif type_mult < 1 and type_mult > 0:
                messages.append(f"   🛡️ **It's not very effective...** ({type_mult}x damage)")
            elif type_mult == 0:
                messages.append(f"   ❌ **It has no effect!** (0x damage)")
            
            if damage > 0:
                messages.append(f"   💥 {defender.pokemon.name.title()} took **{damage} damage**!")
                messages.append(f"   📉 HP: {old_hp} → {defender.current_hp} ({defender.current_hp}/{defender.pokemon.stats.hp})")
                
                # Health status indicator
                hp_percent = (defender.current_hp / defender.pokemon.stats.hp) * 100
                if hp_percent > 75:
                    health_status = "💚 Excellent condition"
                elif hp_percent > 50:
                    health_status = "💛 Good condition"
                elif hp_percent > 25:
                    health_status = "🧡 Injured"
                elif hp_percent > 0:
                    health_status = "❤️ Critically injured"
                else:
                    health_status = "💀 Fainted"
                    
                messages.append(f"   🏥 **Health Status:** {health_status} ({int(hp_percent)}%)")
        else:
            messages.append(f"   ✨ {move_name} is a status move - no direct damage!")
        
        # Status effect application (simplified for now)
        if defender.current_hp > 0:
            status_chance = random.random()
            if any(word in move.name.lower() for word in ["fire", "flame", "burn"]) and status_chance < 0.15:
                status_msg = self.apply_status_effect(defender, StatusEffect.BURN)
                messages.append(f"   🔥 **Status Effect:** {status_msg}")
            elif any(word in move.name.lower() for word in ["poison", "toxic", "sludge"]) and status_chance < 0.15:
                status_msg = self.apply_status_effect(defender, StatusEffect.POISON)
                messages.append(f"   ☠️ **Status Effect:** {status_msg}")
            elif any(word in move.name.lower() for word in ["thunder", "shock", "bolt"]) and status_chance < 0.15:
                status_msg = self.apply_status_effect(defender, StatusEffect.PARALYSIS)
                messages.append(f"   ⚡ **Status Effect:** {status_msg}")
        
        return messages


# Initialize the MCP server
app = Server("pokemon-battle-server")
data_manager = PokemonDataManager()
battle_simulator = BattleSimulator(data_manager)

@app.list_resources()
async def handle_list_resources() -> list[types.Resource]:
    """List available Pokemon data resources"""
    return [
        types.Resource(
            uri="pokemon://database",
            name="Pokemon Database",
            description="Comprehensive Pokemon data including stats, types, abilities, and moves",
            mimeType="application/json"
        ),
        types.Resource(
            uri="pokemon://types",
            name="Pokemon Type Chart",
            description="Type effectiveness chart for Pokemon battles",
            mimeType="application/json"
        )
    ]

@app.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Read Pokemon resource data"""
    if uri == "pokemon://database":
        return json.dumps({
            "description": "Pokemon Database Resource",
            "usage": "Use the get_pokemon tool to fetch specific Pokemon data",
            "available_data": [
                "Base stats (HP, Attack, Defense, Sp. Attack, Sp. Defense, Speed)",
                "Types (Fire, Water, Grass, etc.)",
                "Abilities",
                "Moves and their effects",
                "Height and weight",
                "Sprite images"
            ],
            "example_usage": "Call get_pokemon tool with {'name': 'pikachu'}"
        }, indent=2)
    
    elif uri == "pokemon://types":
        return json.dumps({
            "description": "Pokemon Type Effectiveness Chart",
            "type_chart": data_manager.type_chart,
            "usage": "Use get_type_effectiveness tool to calculate damage multipliers",
            "effectiveness_values": {
                "2.0": "Super effective",
                "1.0": "Normal damage", 
                "0.5": "Not very effective",
                "0.0": "No effect"
            }
        }, indent=2)
    
    else:
        raise ValueError(f"Unknown resource URI: {uri}")

@app.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """List available tools"""
    return [
        types.Tool(
            name="get_pokemon",
            description="Fetch comprehensive data for a specific Pokémon by name or ID. Returns stats, types, abilities, and more.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Pokémon name or ID (e.g., 'pikachu', 'charizard', '25')"
                    }
                },
                "required": ["name"]
            }
        ),
        types.Tool(
            name="battle_simulate",
            description="Simulate a realistic battle between two Pokémon with turn-based combat, type effectiveness, and status effects. Provides a detailed, turn-by-turn log.",
            inputSchema={
                "type": "object",
                "properties": {
                    "pokemon1": {
                        "type": "string",
                        "description": "Name of the first Pokémon"
                    },
                    "pokemon2": {
                        "type": "string", 
                        "description": "Name of the second Pokémon"
                    }
                },
                "required": ["pokemon1", "pokemon2"]
            }
        ),
        types.Tool(
            name="get_type_effectiveness",
            description="Calculate type effectiveness multiplier for attacks. Essential for battle strategy.",
            inputSchema={
                "type": "object",
                "properties": {
                    "attacking_type": {
                        "type": "string",
                        "description": "The type of the attacking move (e.g., 'fire', 'water')"
                    },
                    "defending_types": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "The types of the defending Pokémon (e.g., ['grass', 'poison'])"
                    }
                },
                "required": ["attacking_type", "defending_types"]
            }
        )
    ]

@app.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """Handle tool calls with improved error handling and formatting"""
    logger.info(f"Handling tool call: {name} with arguments: {arguments}")
    
    if name == "get_pokemon":
        pokemon_name = arguments.get("name", "").strip()
        if not pokemon_name:
            return [types.TextContent(type="text", text="❌ Error: Pokemon name is required")]
        
        pokemon = await data_manager.get_pokemon(pokemon_name)
        if not pokemon:
            return [types.TextContent(
                type="text", 
                text=f"❌ Error: Could not find Pokémon '{pokemon_name}'. Please check the spelling or try a different name."
            )]
        
        # Format Pokemon data with better presentation
        total_stats = (pokemon.stats.hp + pokemon.stats.attack + pokemon.stats.defense + 
                      pokemon.stats.special_attack + pokemon.stats.special_defense + pokemon.stats.speed)
        
        result_text = f"🌟 **{pokemon.name.title()}** (#{pokemon.id:03d})\n\n"
        result_text += f"🏷️ **Types:** {' / '.join([t.title() for t in pokemon.types])}\n\n"
        result_text += f"📊 **Base Stats:**\n"
        result_text += f"   ❤️ HP: {pokemon.stats.hp}\n"
        result_text += f"   ⚔️ Attack: {pokemon.stats.attack}\n"
        result_text += f"   🛡️ Defense: {pokemon.stats.defense}\n"
        result_text += f"   🔮 Sp. Attack: {pokemon.stats.special_attack}\n"
        result_text += f"   🛡️ Sp. Defense: {pokemon.stats.special_defense}\n"
        result_text += f"   💨 Speed: {pokemon.stats.speed}\n"
        result_text += f"   📈 **Total: {total_stats}**\n\n"
        result_text += f"⚡ **Abilities:** {', '.join([a.replace('-', ' ').title() for a in pokemon.abilities])}\n\n"
        result_text += f"📏 **Physical:** {pokemon.height / 10:.1f}m tall, {pokemon.weight / 10:.1f}kg\n\n"
        
        if pokemon.moves:
            result_text += f"🥊 **Notable Moves:**\n"
            for move in pokemon.moves[:8]:  # Show first 8 moves
                power_text = f" ({move.power} power)" if move.power else ""
                result_text += f"   • {move.name.replace('-', ' ').title()} ({move.type.title()}{power_text})\n"
        
        return [types.TextContent(type="text", text=result_text)]
    
    elif name == "battle_simulate":
        pokemon1_name = arguments.get("pokemon1", "").strip()
        pokemon2_name = arguments.get("pokemon2", "").strip()
        
        if not pokemon1_name or not pokemon2_name:
            return [types.TextContent(type="text", text="❌ Error: Both pokemon1 and pokemon2 names are required")]
        
        logger.info(f"Starting battle simulation between {pokemon1_name} and {pokemon2_name}")
        
        # FIXED: Use the correct method name and await it properly
        battle_result = await battle_simulator.battle_simulate(pokemon1_name, pokemon2_name)
        
        if "error" in battle_result:
            return [types.TextContent(type="text", text=f"❌ Battle Error: {battle_result['error']}")]
        
        # Format battle result with better presentation
        result_text = "\n".join(battle_result['battle_log'])
        result_text += f"\n\n📋 **Battle Summary:**\n"
        result_text += f"🏆 Winner: **{battle_result['winner']}**\n"
        result_text += f"⏱️ Duration: {battle_result['turns']} turns\n\n"
        
        result_text += f"📊 **Final Status:**\n"
        p1 = battle_result['pokemon1']
        p2 = battle_result['pokemon2']
        
        result_text += f"• {p1['name']}: {p1['final_hp']}/{p1['max_hp']} HP"
        if p1['status'] != 'none':
            result_text += f" ({p1['status']})"
        result_text += "\n"
        
        result_text += f"• {p2['name']}: {p2['final_hp']}/{p2['max_hp']} HP"
        if p2['status'] != 'none':
            result_text += f" ({p2['status']})"
        result_text += "\n"
        
        return [types.TextContent(type="text", text=result_text)]
    
    elif name == "get_type_effectiveness":
        attacking_type = arguments.get("attacking_type", "").strip().lower()
        defending_types = arguments.get("defending_types", [])
        
        if not attacking_type or not defending_types:
            return [types.TextContent(type="text", text="❌ Error: Both attacking_type and defending_types are required")]
        
        # Ensure defending_types is a list
        if isinstance(defending_types, str):
            defending_types = [defending_types.strip().lower()]
        else:
            defending_types = [t.strip().lower() for t in defending_types]
        
        effectiveness = data_manager.get_type_effectiveness(attacking_type, defending_types)
        
        # Determine effectiveness description with emojis
        if effectiveness >= 4:
            description = "🔥🔥 Extremely effective!"
            emoji = "🔥🔥"
        elif effectiveness >= 2:
            description = "🔥 Super effective!"
            emoji = "🔥"
        elif effectiveness == 1:
            description = "➖ Normal damage"
            emoji = "➖"
        elif effectiveness > 0:
            description = "🛡️ Not very effective"
            emoji = "🛡️"
        else:
            description = "❌ No effect!"
            emoji = "❌"
        
        result_text = f"⚡ **TYPE EFFECTIVENESS ANALYSIS**\n\n"
        result_text += f"🎯 **{attacking_type.title()}** → **{' + '.join([t.title() for t in defending_types])}**\n\n"
        result_text += f"{emoji} **Effectiveness:** {effectiveness}x\n"
        result_text += f"📈 **Result:** {description}\n"
        result_text += f"💪 **Damage:** {int(effectiveness * 100)}% of normal\n\n"
        
        # Strategic advice
        if effectiveness > 1:
            result_text += "✅ **Strategy:** This is an excellent offensive choice! Use this type advantage!\n"
        elif effectiveness < 1 and effectiveness > 0:
            result_text += "❌ **Strategy:** This is a poor offensive choice. Consider a different move type.\n"
        elif effectiveness == 0:
            result_text += "🚫 **Strategy:** This move will have absolutely no effect. Choose a different attack!\n"
        else:
            result_text += "⚖️ **Strategy:** Standard damage - no particular advantage or disadvantage.\n"
        
        return [types.TextContent(type="text", text=result_text)]
    
    else:
        return [types.TextContent(type="text", text=f"❌ Error: Unknown tool '{name}'")]

async def main():
    """Main entry point for the MCP server"""
    from mcp.server.stdio import stdio_server
    
    logger.info("🎮 Starting Pokemon MCP Server...")
    
    stdio = stdio_server()
    read_stream, write_stream = await stdio.__aenter__()
    
    try:
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )
    finally:
        await stdio.__aexit__(None, None, None)

if __name__ == "__main__":
    asyncio.run(main())