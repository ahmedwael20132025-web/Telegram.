"""تجميع كل راوترات لوحة الأدمن."""
from aiogram import Router

from handlers.admin import (
    broadcast,
    channels,
    coupons,
    files,
    finance_ops,
    pages,
    panel,
    payments,
    project_generator_admin,
    users,
    vip,
)

admin_router = Router(name="admin")
admin_router.include_router(panel.router)
admin_router.include_router(users.router)
admin_router.include_router(broadcast.router)
admin_router.include_router(payments.router)
admin_router.include_router(files.router)
admin_router.include_router(channels.router)
admin_router.include_router(pages.router)
admin_router.include_router(vip.router)
admin_router.include_router(coupons.router)
admin_router.include_router(finance_ops.router)
admin_router.include_router(project_generator_admin.router)
