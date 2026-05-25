from aiogram.fsm.state import State, StatesGroup


class GuestFlow(StatesGroup):
    AWAITING_FEEDBACK = State()
    IN_INTERVIEW = State()
    FINALIZING = State()


class AdminFlow(StatesGroup):
    IDLE = State()
    AWAITING_QUESTION_TEXT = State()
    AWAITING_QUESTION_METRIC = State()
    AWAITING_QUESTION_EDIT = State()
