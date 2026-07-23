"""Public resource status and reconciliation routes."""

from __future__ import annotations

from typing import Protocol

from fastapi import APIRouter, Path, status

from .concurrency import run_sync
from .resource_types import (
    OPERATION_ID_RE,
    ResourceOperation,
    ResourceProfile,
    ResourceSnapshot,
    Workload,
)
from .schemas import (
    ResourceOperationResponse,
    ResourceReconcileInput,
    ResourceSnapshotResponse,
)


class ResourceControl(Protocol):
    def snapshot(self) -> ResourceSnapshot: ...

    def reconcile(self, profile: ResourceProfile) -> ResourceOperation: ...

    def reset(self, workload: Workload) -> ResourceOperation: ...

    def operation(self, operation_id: str) -> ResourceOperation: ...


def build_resource_routers(
    control: ResourceControl,
) -> tuple[APIRouter, APIRouter]:
    router = APIRouter(prefix="/api/v1/resources", tags=["資源"])
    operations = APIRouter(
        prefix="/api/v1/resource-operations",
        tags=["資源"],
    )

    @router.get(
        "",
        response_model=ResourceSnapshotResponse,
        summary="查看推論資源狀態",
        description="輸入：無。輸出：資源策略、目標 profile、各 workload 與目前操作。",
    )
    async def resources() -> ResourceSnapshotResponse:
        snapshot = await run_sync(control.snapshot)
        return ResourceSnapshotResponse.model_validate(snapshot.to_dict())

    @router.post(
        "/reconcile",
        response_model=ResourceOperationResponse,
        status_code=status.HTTP_202_ACCEPTED,
        summary="套用推論資源 profile",
        description="輸入：固定資源 profile。輸出：可輪詢的非同步操作。",
    )
    async def reconcile(
        body: ResourceReconcileInput,
    ) -> ResourceOperationResponse:
        operation = await run_sync(control.reconcile, body.profile)
        return ResourceOperationResponse.model_validate(operation.to_dict())

    @router.post(
        "/{workload}/reset",
        response_model=ResourceOperationResponse,
        status_code=status.HTTP_202_ACCEPTED,
        summary="重置單一推論 workload",
        description="輸入：固定 workload。輸出：依目前策略執行的可輪詢重置操作。",
    )
    async def reset(workload: Workload) -> ResourceOperationResponse:
        operation = await run_sync(control.reset, workload)
        return ResourceOperationResponse.model_validate(operation.to_dict())

    @operations.get(
        "/{operation_id}",
        response_model=ResourceOperationResponse,
        summary="查看資源操作進度",
        description="輸入：資源操作識別碼。輸出：目前 phase 與有限錯誤狀態。",
    )
    async def operation(
        operation_id: str = Path(pattern=OPERATION_ID_RE.pattern),
    ) -> ResourceOperationResponse:
        current = await run_sync(control.operation, operation_id)
        return ResourceOperationResponse.model_validate(current.to_dict())

    return router, operations
