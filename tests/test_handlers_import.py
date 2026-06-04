"""Smoke-проверка: все router'ы импортируются и регистрируют handler'ы."""


def test_guest_handlers_import() -> None:
    from channels.telegram.guest_bot.handlers import feedback, start

    assert start.router.name == "guest_start"
    assert feedback.router.name == "guest_feedback"


def test_admin_handlers_import() -> None:
    from presentations.telegram_admin.handlers import auth, questions

    assert auth.router.name == "admin_auth"
    assert questions.router.name == "admin_questions"


def test_fsm_states_import() -> None:
    from channels.telegram.common.fsm.states import AdminFlow, GuestFlow

    assert GuestFlow.AWAITING_FEEDBACK is not None
    assert AdminFlow.IDLE is not None
