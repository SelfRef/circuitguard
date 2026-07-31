import logging

from circuitguard.bot import CircuitGuardBot
from circuitguard.config import Settings


def main() -> None:
    settings = Settings()  # type: ignore[call-arg]
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )
    bot = CircuitGuardBot(settings)
    bot.run(settings.discord_token.get_secret_value(), log_handler=None)


if __name__ == "__main__":
    main()
