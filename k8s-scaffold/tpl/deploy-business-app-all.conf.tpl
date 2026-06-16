# ============================================================================
# __APP_TITLE__ App 业务应用配置
# ============================================================================
__APP_UPPER___APP_PROJECT_ID="sunmoonai"
__APP_UPPER___APP_NAMESPACE="app-platform-dev"
ENVIRONMENT="development"
__APP_UPPER___APP_IMAGE_TAG="${__APP_UPPER___APP_IMAGE_TAG:-1.0.0}"

# App 源码根目录。Backend 的资源声明随源码维护。
__APP_UPPER___APP_SOURCE_ROOT="${__APP_UPPER___APP_SOURCE_ROOT:-${HOME}/__APP__-app}"

# Backend 能力默认完整启用；是否启动组件由下面的集群开关决定。
__APP___admin_backend_database_access_enabled="true"
__APP___admin_backend_storage_access_enabled="true"
__APP___admin_backend_search_access_enabled="true"
__APP___web_backend_database_access_enabled="true"
__APP___web_backend_storage_access_enabled="true"
__APP___web_backend_search_access_enabled="true"

__APP___admin_backend_configured="true"
__APP___admin_frontend_configured="true"
__APP___web_backend_configured="true"
__APP___web_frontend_configured="true"
celeryworker___APP___admin_backend_configured="true"
nodebullworker___APP___web_backend_configured="true"

C1___APP___admin_backend_enabled="true"
C2___APP___admin_backend_enabled="false"
C3___APP___admin_backend_enabled="false"
KIND___APP___admin_backend_enabled="true"

C1___APP___admin_frontend_enabled="true"
C2___APP___admin_frontend_enabled="false"
C3___APP___admin_frontend_enabled="false"
KIND___APP___admin_frontend_enabled="true"

C1___APP___web_backend_enabled="true"
C2___APP___web_backend_enabled="false"
C3___APP___web_backend_enabled="false"
KIND___APP___web_backend_enabled="true"

C1___APP___web_frontend_enabled="true"
C2___APP___web_frontend_enabled="false"
C3___APP___web_frontend_enabled="false"
KIND___APP___web_frontend_enabled="true"

C1_celeryworker___APP___admin_backend_enabled="false"
C2_celeryworker___APP___admin_backend_enabled="false"
C3_celeryworker___APP___admin_backend_enabled="false"
KIND_celeryworker___APP___admin_backend_enabled="false"

C1_nodebullworker___APP___web_backend_enabled="false"
C2_nodebullworker___APP___web_backend_enabled="false"
C3_nodebullworker___APP___web_backend_enabled="false"
KIND_nodebullworker___APP___web_backend_enabled="false"

C1___APP___admin_backend_priority=900
C2___APP___admin_backend_priority=900
C3___APP___admin_backend_priority=900
KIND___APP___admin_backend_priority=900

C1_celeryworker___APP___admin_backend_priority=890
C2_celeryworker___APP___admin_backend_priority=890
C3_celeryworker___APP___admin_backend_priority=890
KIND_celeryworker___APP___admin_backend_priority=890

C1___APP___admin_frontend_priority=800
C2___APP___admin_frontend_priority=800
C3___APP___admin_frontend_priority=800
KIND___APP___admin_frontend_priority=800

C1___APP___web_backend_priority=700
C2___APP___web_backend_priority=700
C3___APP___web_backend_priority=700
KIND___APP___web_backend_priority=700

C1_nodebullworker___APP___web_backend_priority=690
C2_nodebullworker___APP___web_backend_priority=690
C3_nodebullworker___APP___web_backend_priority=690
KIND_nodebullworker___APP___web_backend_priority=690

C1___APP___web_frontend_priority=600
C2___APP___web_frontend_priority=600
C3___APP___web_frontend_priority=600
KIND___APP___web_frontend_priority=600
