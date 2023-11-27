class ConfigException(Exception):
    def __init__(self):
        """
        To be used when a user is not correctly configured
        when executing a `bet` command.
        """
        pass

class BetValueException(Exception):
    def __init__(self, value):
        """
        To be used when a user is not correctly configured
        when executing a `bet` command.
        """
        self.value = value
        pass

class BalanceException(Exception):
    def __init__(self, balance, value):
        """
        To be used when a user does not have a valid
        balance for the `bet` placed.
        """
        self.balance = balance
        self.value = value

class LobbyTypeException(Exception):
    def __init__(self):
        """
        To be used when the game bet on is not a valid
        lobby type for the `bet`.
        """
        # Add in the lobby type parameters
        pass

class BetTimeException(Exception):
    def __init__(self, start, end, bet):
        """
        To be used when the user bet on a game that at
        an invalid time (usually after the game).
        """
        self.start = start
        self.bet = bet
        self.end = end

class NoBetsException(Exception):
    def __init__(self):
        """
        To be used when the game bet on is not a valid
        lobby type for the `bet`.
        """
        # Add in the lobby type parameters
        pass