class DomainError(Exception):
    """Base class for all business-logic errors."""
    pass

class CityNotFoundError(DomainError):
    """Raised when a city cannot be resolved by the geocoder."""
    def __init__(self, city_name: str):
        self.city_name = city_name
        super().__init__(f"City not found: {city_name}")

class UserAlreadyExistsError(DomainError):
    """Raised when trying to register a user who is already in the system."""
    pass
