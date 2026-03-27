import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class WorkflowError(Exception):
    pass


def load_config(source: Optional[str] = None) -> Dict[str, Any]:
    """
    Загрузить конфигурацию workflow.
    По умолчанию возвращает пример конфигурации.
    """
    # Здесь можно заменить на реальную загрузку из файла/сервиса
    if source:
        logger.info("Loading config from %s", source)
    return {
        "name": "example",
        "steps": [
            {"id": "start", "type": "init"},
            {"id": "process", "type": "task", "retries": 2},
            {"id": "end", "type": "finish"},
        ],
    }


def validate_config(cfg: Dict[str, Any]) -> None:
    """
    Проверить корректность конфигурации workflow.
    Бросает WorkflowError при ошибках.
    """
    if "name" not in cfg or "steps" not in cfg:
        raise WorkflowError("Invalid config: missing 'name' or 'steps'")
    if not isinstance(cfg["steps"], list) or len(cfg["steps"]) == 0:
        raise WorkflowError("Invalid config: 'steps' must be a non-empty list")
    ids = set()
    for step in cfg["steps"]:
        sid = step.get("id")
        if not sid:
            raise WorkflowError("Step without 'id' found")
        if sid in ids:
            raise WorkflowError(f"Duplicate step id: {sid}")
        ids.add(sid)


def run_step(step: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Выполнить один шаг. Возвращает обновлённый context.
    Заглушка: можно расширять по type/handler.
    """
    sid = step.get("id")
    stype = step.get("type", "task")
    logger.info("Running step %s (type=%s)", sid, stype)

    # Примеры поведения по типу шага
    if stype == "init":
        context["started"] = True
        context["last_step"] = sid
        return context
    if stype == "task":
        # эмулируем задачу, поддержка retries
        retries = step.get("retries", 0)
        attempt = 0
        while True:
            attempt += 1
            try:
                # реальная логика здесь
                context.setdefault("tasks", []).append({"id": sid, "attempt": attempt})
                context["last_step"] = sid
                # если нужно, выбросить исключение для теста:
                # raise RuntimeError("simulated failure")
                return context
            except Exception as e:
                logger.warning("Step %s failed on attempt %d: %s", sid, attempt, e)
                if attempt > retries:
                    raise
                logger.info("Retrying step %s (attempt %d)", sid, attempt + 1)
    if stype == "finish":
        context["finished"] = True
        context["last_step"] = sid
        return context

    # default behavior
    context["last_step"] = sid
    return context


def run_workflow(cfg: Dict[str, Any], initial_context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Основная логика выполнения workflow: валидирует конфиг и выполняет шаги последовательно.
    Возвращает итоговый context.
    """
    validate_config(cfg)
    context: Dict[str, Any] = initial_context.copy() if initial_context else {}
    logger.info("Starting workflow '%s'", cfg.get("name"))

    for step in cfg["steps"]:
        try:
            context = run_step(step, context)
        except Exception as e:
            logger.error("Error in step %s: %s", step.get("id"), e)
            # Поведение при ошибке: останавливаем workflow и пробрасываем ошибку
            raise

    logger.info("Workflow '%s' finished. Context: %s", cfg.get("name"), context)
    return context


def main() -> int:
    """
    Точка входа для запуска из командной строки.
    Возвращает код выхода процесса.
    """
    try:
        cfg = load_config()
        result = run_workflow(cfg)
        logger.info("Result: %s", result)
        return 0
    except WorkflowError as we:
        logger.error("Workflow configuration error: %s", we)
        return 2
    except Exception as e:
        logger.exception("Unhandled error while running workflow: %s", e)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
