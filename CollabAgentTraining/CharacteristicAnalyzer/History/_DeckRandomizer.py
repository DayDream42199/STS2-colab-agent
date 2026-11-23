import random

random.seed(67)

Deck = ["Strike"] * 4 + ["Defend"] * 5 + ["Bash"]

CardCost = {
    "Strike": 1,
    "Defend": 1,
    "Bash": 2
}


CardDefinition = {
    "Strike": [1, 6, 0, ["aggressive", "now", "team"]],
    "Defend": [1, 0, 5, ["defensive", "now", "self"]],
    "Bash": [2, 8, 0, ["aggressive", "now", "team"]]
}


DrawPile = Deck.copy()
random.shuffle(DrawPile)

Hand = []
DiscardPile = []
UsedCards = []


def draw_card(amount):
    global DrawPile

    for i in range(amount):
        if not DrawPile:
            DrawPile = DiscardPile.copy()
            random.shuffle(DrawPile)
            DiscardPile.clear()

        if DrawPile:
            Hand.append(DrawPile.pop(0))


def end_turn():
    DiscardPile.extend(Hand)
    Hand.clear()
    UsedCards.clear()


def randomizeIntent():
    return random.choice([0, 5, 10])


def play_aggressive(energy):
    # Prioritize Bash > Strike > Defend
    while energy > 0 and Hand:

        if "Bash" in Hand and energy >= CardCost["Bash"]:
            Hand.remove("Bash")
            DiscardPile.append("Bash")
            UsedCards.append("Bash")
            energy -= CardCost["Bash"]

        elif "Strike" in Hand and energy >= CardCost["Strike"]:
            Hand.remove("Strike")
            DiscardPile.append("Strike")
            UsedCards.append("Strike")
            energy -= CardCost["Strike"]

        elif "Defend" in Hand and energy >= CardCost["Defend"]:
            Hand.remove("Defend")
            DiscardPile.append("Defend")
            UsedCards.append("Defend")
            energy -= CardCost["Defend"]

        else:
            break

    return energy

def play_defensive(energy):
    # Prioritize Defend > Strike > Bash
    while energy > 0 and Hand:

        if "Defend" in Hand and energy >= CardCost["Defend"]:
            Hand.remove("Defend")
            DiscardPile.append("Defend")
            UsedCards.append("Defend")
            energy -= CardCost["Defend"]

        elif "Strike" in Hand and energy >= CardCost["Strike"]:
                    Hand.remove("Strike")
                    DiscardPile.append("Strike")
                    UsedCards.append("Strike")
                    energy -= CardCost["Strike"]
        
        elif "Bash" in Hand and energy >= CardCost["Bash"]:
            Hand.remove("Bash")
            DiscardPile.append("Bash")
            UsedCards.append("Bash")
            energy -= CardCost["Bash"]

        else:
            break

    return energy

def play_cheese(energy, intent):
    # Prioritize Defend > Strike > Bash
    block_now = 0
    while energy > 0 and Hand:

        if "Defend" in Hand and energy >= CardCost["Defend"] and intent > block_now:
            Hand.remove("Defend")
            DiscardPile.append("Defend")
            UsedCards.append("Defend")
            energy -= CardCost["Defend"]

            block_now += 5

        elif "Strike" in Hand and energy >= CardCost["Strike"]:
                    Hand.remove("Strike")
                    DiscardPile.append("Strike")
                    UsedCards.append("Strike")
                    energy -= CardCost["Strike"]
        
        elif "Bash" in Hand and energy >= CardCost["Bash"]:
            Hand.remove("Bash")
            DiscardPile.append("Bash")
            UsedCards.append("Bash")
            energy -= CardCost["Bash"]

        else:
            break

    return energy

def play_random(energy):
    while energy > 0 and Hand:
     
        playable_cards = [
            card for card in Hand
            if CardCost[card] <= energy
        ]

        if not playable_cards:
            break

        card = random.choice(playable_cards)

        Hand.remove(card)
        DiscardPile.append(card)
        UsedCards.append(card)

        energy -= CardCost[card]
     
    return energy

def play_change(energy, iteration):
    if iteration < 10:
        play_aggressive(energy)
    else:
        play_defensive(energy)

turnData = []

for i in range(100):
    energy = 3

    draw_card(5)
    intent = randomizeIntent()
    energy = play_change(energy, i)

    DefinedUsedCards = [CardDefinition[card] for card in UsedCards]
    DefinedHand = [CardDefinition[card] for card in Hand]

    print(f"[3, {DefinedUsedCards}, {DefinedHand + DefinedUsedCards}, {intent}],")

    end_turn()