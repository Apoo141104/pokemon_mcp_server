import httpx
import logging
from typing import Any, Dict, List, Optional, Sequence
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger("pokemon-mcp-server")

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
                response = await client.get(f"https://pokeapi.co/api/v2/pokemon/{identifier}")
                if response.status_code != 200:
                    logger.error(f"Failed to fetch Pokémon {identifier}: {response.status_code}")
                    return None
                
                data = response.json()
                
                stats = PokemonStats(
                    hp=next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "hp"),
                    attack=next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "attack"),
                    defense=next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "defense"),
                    special_attack=next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "special-attack"),
                    special_defense=next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "special-defense"),
                    speed=next(s["base_stat"] for s in data["stats"] if s["stat"]["name"] == "speed")
                )
                
                types_list = [t["type"]["name"] for t in data["types"]]
                abilities = [a["ability"]["name"] for a in data["abilities"]]
                
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