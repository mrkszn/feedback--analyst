from aiogram.fsm.state import State, StatesGroup


class GuestFlow(StatesGroup):
    AWAITING_FEEDBACK = State()
    IN_DIALOGUE = State()
    AWAITING_SURVEY_CONSENT = State()
    IN_INTERVIEW = State()
    FINALIZING = State()


class AdminFlow(StatesGroup):
    IDLE = State()
    AWAITING_QUESTION_TEXT = State()
    AWAITING_QUESTION_METRIC = State()
    AWAITING_QUESTION_EDIT = State()
    AWAITING_QUESTION_COUNT = State()
    AWAITING_QUESTION_VOICE = State()
    AWAITING_DRAFT_EDIT = State()
    AWAITING_NL_DESCRIPTION = State()
    AWAITING_NL_CONFIRMATION = State()
