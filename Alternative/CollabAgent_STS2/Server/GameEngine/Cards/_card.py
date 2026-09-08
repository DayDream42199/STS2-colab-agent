from abc import ABC, abstractmethod
from ._card_properties import CardProperties

class Card(ABC):
    def __init__(
        self,
        card_id,
        name,
        card_type,
        card_class,
        rarity,
        cost,
        target_type,
        properties=None
    ):
        self.card_id = card_id
        self.name = name
        self.card_type = card_type
        # Class and rarity are separate axes; neither implies the other.
        self.card_class = card_class
        self.rarity = rarity
        self.cost = cost
        self.target_type = target_type

        self.properties = properties if properties is not None else CardProperties()

    @abstractmethod
    def get_effects(self, context):
        pass