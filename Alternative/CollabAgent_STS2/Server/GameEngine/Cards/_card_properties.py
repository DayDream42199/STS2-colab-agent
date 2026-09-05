class CardProperties:
    def __init__(
        self,
        exhaust=False,
        retain=False,
        innate=False,
        ethereal=False,
        playable=True
    ):
        self.exhaust = exhaust
        self.retain = retain
        self.innate = innate
        self.ethereal = ethereal
        self.playable = playable