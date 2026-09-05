from abc import ABC, abstractmethod
from ._card_properties import CardProperties

class Card(ABC):
    def __init__(
        self,
        card_id,
        name,
        card_type,
        rarity,
        cost,
        target_type,
        properties=None
    ):
        self.card_id = card_id
        self.name = name
        self.card_type = card_type
        self.rarity = rarity
        self.cost = cost
        self.target_type = target_type

        self.properties = properties if properties is not None else CardProperties()

    @abstractmethod
    def get_effects(self, context):
        pass