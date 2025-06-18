from pydantic import BaseModel

class UserProfile(BaseModel):
    notice_period: str
    current_ctc: str
    expected_ctc: str
    preferred_location: str
    work_authorization: str
    relocation_willingness: str