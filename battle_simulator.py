import asyncio
import json
import logging
import random
import math
from typing import Any, Dict, List, Optional, Tuple, Sequence
from dataclasses import dataclass, asdict
from enum import Enum
from pokemon_data import Pokemon, PokemonStats, Move, StatusEffect, PokemonDataManager

logger = logging.getLogger("pokemon-mcp-server")

@dataclass
class BattlePokemon:
    pokemon: Pokemon
    current_hp: int
    status: StatusEffect = StatusEffect.NONE
    status_turns: int = 0
    
    def __post_init__(self):
        if self.current_hp == 0:
            self.current_hp = self.pokemon.stats.hp

class BattleSimulator:
    """Handles Pokémon battle simulation - IMPROVED VERSION"""
    
    def __init__(self, data_manager: PokemonDataManager):
        self.data_manager = data_manager
        
    def calculate_damage(self, attacker: BattlePokemon, defender: BattlePokemon, move: Move) -> int:
        """Calculate damage dealt by a move using accurate Pokémon damage formula"""
        if move.power is None:
            return 0
        
        level = 50
        
        if move.category == "physical":
            attack_stat = attacker.pokemon.stats.attack
            defense_stat = defender.pokemon.stats.defense
        elif move.category == "special":
            attack_stat = attacker.pokemon.stats.special_attack
            defense_stat = defender.pokemon.stats.special_defense
        else:
            return 0
        
        if attacker.status == StatusEffect.BURN and move.category == "physical":
            attack_stat = attack_stat // 2
        
        base_damage = ((((2 * level + 10) / 250) * (attack_stat / defense_stat) * move.power) + 2)
        
        type_multiplier = self.data_manager.get_type_effectiveness(move.type, defender.pokemon.types)
        base_damage *= type_multiplier
        
        if move.type in attacker.pokemon.types:
            base_damage *= 1.5
        
        base_damage *= random.uniform(0.85, 1.0)
        
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
            if pokemon.status_turns >= random.randint(1, 3):
                pokemon.status = StatusEffect.NONE
                pokemon.status_turns = 0
                messages.append(f"😴 {pokemon.pokemon.name.title()} woke up!")
        
        elif pokemon.status == StatusEffect.FREEZE:
            if random.random() < 0.2:
                pokemon.status = StatusEffect.NONE
                pokemon.status_turns = 0
                messages.append(f"🧊 {pokemon.pokemon.name.title()} thawed out!")
        
        return messages
    
    def select_move(self, pokemon: BattlePokemon, opponent: BattlePokemon) -> Optional[Move]:
        """Intelligently select a move for battle"""
        available_moves = [move for move in pokemon.pokemon.moves if move.power and move.power > 0]
        
        if not available_moves:
            return None
        
        best_moves = []
        best_effectiveness = 0
        
        for move in available_moves:
            effectiveness = self.data_manager.get_type_effectiveness(move.type, opponent.pokemon.types)
            if effectiveness > best_effectiveness:
                best_effectiveness = effectiveness
                best_moves = [move]
            elif effectiveness == best_effectiveness:
                best_moves.append(move)
        
        if len(best_moves) > 1:
            best_moves.sort(key=lambda m: m.power or 0, reverse=True)
        
        return best_moves[0] if best_moves else random.choice(available_moves)
    
    async def battle_simulate(self, pokemon1_name: str, pokemon2_name: str) -> Dict[str, Any]:
        """Enhanced battle simulation with detailed structured output"""
        logger.info(f"Starting enhanced battle simulation between {pokemon1_name} and {pokemon2_name}")
        
        pokemon1_data = await self.data_manager.get_pokemon(pokemon1_name)
        pokemon2_data = await self.data_manager.get_pokemon(pokemon2_name)
        
        if not pokemon1_data:
            logger.error(f"Could not find Pokémon: {pokemon1_name}")
            return {"error": f"Could not find Pokémon: {pokemon1_name}"}
        if not pokemon2_data:
            logger.error(f"Could not find Pokémon: {pokemon2_name}")
            return {"error": f"Could not find Pokémon: {pokemon2_name}"}
        
        logger.info(f"Found both Pokémon: {pokemon1_data.name} and {pokemon2_data.name}")
        
        battle_pokemon1 = BattlePokemon(pokemon1_data, pokemon1_data.stats.hp)
        battle_pokemon2 = BattlePokemon(pokemon2_data, pokemon2_data.stats.hp)
        
        battle_log = []
        battle_log.append("=" * 80)
        battle_log.append("🎮 **POKÉMON BATTLE ARENA**")
        battle_log.append("=" * 80)
        battle_log.append("")
        
        battle_log.append("### 📋 **Battle Participants**")
        battle_log.append("")
        
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
            for move in pokemon1_data.moves[:6]:
                power_text = f" ({move.power} power)" if move.power else " (Status)"
                battle_log.append(f"     • {move.name.replace('-', ' ').title()} - {move.type.title()}{power_text}")
        battle_log.append("")
        
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
            for move in pokemon2_data.moves[:6]:
                power_text = f" ({move.power} power)" if move.power else " (Status)"
                battle_log.append(f"     • {move.name.replace('-', ' ').title()} - {move.type.title()}{power_text}")
        battle_log.append("")
        
        battle_log.append("### ⚔️ **Battle Conditions**")
        battle_log.append(f"🎯 **Battle Level:** 50 (Standard)")
        battle_log.append(f"🏟️ **Arena:** Standard Battle Arena")
        battle_log.append(f"📏 **Max Turns:** 50")
        battle_log.append("")
        
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
            
            hp1_percent = int((battle_pokemon1.current_hp / pokemon1_data.stats.hp) * 100)
            hp2_percent = int((battle_pokemon2.current_hp / pokemon2_data.stats.hp) * 100)
            
            turn_log.append(f"💖 **HP Status:**")
            turn_log.append(f"   🔵 {pokemon1_data.name.title()}: {battle_pokemon1.current_hp}/{pokemon1_data.stats.hp} HP ({hp1_percent}%)")
            turn_log.append(f"   🔴 {pokemon2_data.name.title()}: {battle_pokemon2.current_hp}/{pokemon2_data.stats.hp} HP ({hp2_percent}%)")
            turn_log.append("")
            
            first_pokemon, second_pokemon = self._determine_turn_order(battle_pokemon1, battle_pokemon2)
            
            if first_pokemon.current_hp > 0:
                turn_log.append(f"🎯 **{first_pokemon.pokemon.name.title()}'s Turn:**")
                messages = await self._execute_detailed_turn(first_pokemon, second_pokemon, turn_log)
                turn_log.extend(messages)
                
                if second_pokemon.current_hp <= 0:
                    turn_log.append(f"💀 **{second_pokemon.pokemon.name.title()} has fainted!**")
                    break
            
            turn_log.append("")
            
            if second_pokemon.current_hp > 0:
                turn_log.append(f"🎯 **{second_pokemon.pokemon.name.title()}'s Turn:**")
                messages = await self._execute_detailed_turn(second_pokemon, first_pokemon, turn_log)
                turn_log.extend(messages)
                
                if first_pokemon.current_hp <= 0:
                    turn_log.append(f"💀 **{first_pokemon.pokemon.name.title()} has fainted!**")
                    break
            
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
        
        battle_log.append("\n" + "=" * 80)
        battle_log.append("🏆 **BATTLE CONCLUSION**")
        battle_log.append("=" * 80)
        
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
        
        battle_log.append("### 📊 **Battle Statistics**")
        battle_log.append(f"🔥 **Total Turns:** {turn}")
        battle_log.append(f"⚡ **Faster Pokémon:** {pokemon1_data.name.title() if speed1 >= speed2 else pokemon2_data.name.title()}")
        battle_log.append(f"💪 **Higher Attack:** {pokemon1_data.name.title() if pokemon1_data.stats.attack >= pokemon2_data.stats.attack else pokemon2_data.name.title()}")
        battle_log.append(f"🛡️ **Higher Defense:** {pokemon1_data.name.title() if pokemon1_data.stats.defense >= pokemon2_data.stats.defense else pokemon2_data.name.title()}")
        battle_log.append("")
        
        battle_log.append("### 🧠 **Strategic Analysis**")
        if winner != "Draw (Time Limit Reached)":
            winner_data = pokemon1_data if winner == pokemon1_data.name.title() else pokemon2_data
            loser_data = pokemon2_data if winner == pokemon1_data.name.title() else pokemon1_data
            
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
        
        if attacker.status == StatusEffect.PARALYSIS and random.random() < 0.25:
            messages.append(f"   ⚡ {attacker.pokemon.name.title()} is paralyzed and cannot move!")
            return messages
        
        if attacker.status == StatusEffect.SLEEP:
            messages.append(f"   😴 {attacker.pokemon.name.title()} is fast asleep and cannot move!")
            return messages
            
        if attacker.status == StatusEffect.FREEZE:
            messages.append(f"   🧊 {attacker.pokemon.name.title()} is frozen solid and cannot move!")
            return messages
        
        move = self.select_move(attacker, defender)
        if not move:
            messages.append(f"   ❌ {attacker.pokemon.name.title()} has no usable moves!")
            return messages
        
        move_name = move.name.replace('-', ' ').title()
        messages.append(f"   🎯 **Move Selected:** {move_name}")
        messages.append(f"   🏷️ **Move Type:** {move.type.title()} ({move.category.title()})")
        if move.power:
            messages.append(f"   💪 **Base Power:** {move.power}")
        messages.append(f"   🎯 **Accuracy:** {move.accuracy}%")
        messages.append("")
        
        accuracy_roll = random.randint(1, 100)
        if accuracy_roll > move.accuracy:
            messages.append(f"   🎲 **Accuracy Roll:** {accuracy_roll}/{move.accuracy} - **MISSED!**")
            messages.append(f"   ❌ {attacker.pokemon.name.title()} used {move_name} but it missed!")
            return messages
        
        messages.append(f"   🎲 **Accuracy Roll:** {accuracy_roll}/{move.accuracy} - **HIT!**")
        messages.append(f"   ⚡ **{attacker.pokemon.name.title()} used {move_name}!**")
        messages.append("")
        
        if move.power:
            damage = self.calculate_damage(attacker, defender, move)
            type_mult = self.data_manager.get_type_effectiveness(move.type, defender.pokemon.types)
            
            messages.append(f"   🧮 **Damage Calculation:**")
            messages.append(f"     📊 Base Power: {move.power}")
            
            if move.category == "physical":
                messages.append(f"     ⚔️ Attack Stat: {attacker.pokemon.stats.attack}")
                messages.append(f"     🛡️ Defense Stat: {defender.pokemon.stats.defense}")
            else:
                messages.append(f"     🔮 Sp. Attack Stat: {attacker.pokemon.stats.special_attack}")
                messages.append(f"     🛡️ Sp. Defense Stat: {defender.pokemon.stats.special_defense}")
            
            messages.append(f"     🎯 Type Effectiveness: {type_mult}x")
            
            if move.type in attacker.pokemon.types:
                messages.append(f"     ⭐ STAB (Same Type Attack Bonus): 1.5x")
            
            messages.append(f"     💥 **Final Damage: {damage}**")
            messages.append("")
            
            old_hp = defender.current_hp
            defender.current_hp = max(0, defender.current_hp - damage)
            
            if type_mult > 1:
                messages.append(f"   🔥 **It's super effective!** ({type_mult}x damage)")
            elif type_mult < 1 and type_mult > 0:
                messages.append(f"   🛡️ **It's not very effective...** ({type_mult}x damage)")
            elif type_mult == 0:
                messages.append(f"   ❌ **It has no effect!** (0x damage)")
            
            if damage > 0:
                messages.append(f"   💥 {defender.pokemon.name.title()} took **{damage} damage**!")
                messages.append(f"   📉 HP: {old_hp} → {defender.current_hp} ({defender.current_hp}/{defender.pokemon.stats.hp})")
                
                hp_percent = (defender.current_hp / defender.pokemon.stats.hp) * 100
                if hp_percent > 75:
                    health_status = "💚 Excellent condition"
                elif hp_percent > 50:
                    health_status = "💛 Good condition"
                elif hp_percent > 25:
                    health_status = "🧡 Below average condition"
                else:
                    health_status = "💔 Critical condition"
                messages.append(f"   🩺 **Health Status:** {health_status}")

            if defender.current_hp <= 0:
                messages.append(f"   💀 **{defender.pokemon.name.title()} has fainted!**")
                return messages
        
        if move.effect and "burns" in move.effect.lower():
            if defender.status == StatusEffect.NONE:
                messages.append(f"   🔥 **{self.apply_status_effect(defender, StatusEffect.BURN)}**")
        elif move.effect and "poisons" in move.effect.lower():
            if defender.status == StatusEffect.NONE:
                messages.append(f"   ☠️ **{self.apply_status_effect(defender, StatusEffect.POISON)}**")
        elif move.effect and "paralyzes" in move.effect.lower():
            if defender.status == StatusEffect.NONE:
                messages.append(f"   ⚡ **{self.apply_status_effect(defender, StatusEffect.PARALYSIS)}**")
        
        return messages