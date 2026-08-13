apiVersion: batch/v1
kind: Job
metadata:
  name: __APP__-backend-migration-__RELEASE_ID__
  namespace: __NAMESPACE__
  labels:
    app.kubernetes.io/name: __APP__-backend
    app.kubernetes.io/component: backend-migration
    app.kubernetes.io/part-of: __APP__
    sunmoonai.com/app: __APP__
    sunmoonai.com/managed-by: architecture-v2
    sunmoonai.com/release-id: __RELEASE_ID__
spec:
  backoffLimit: 0
  activeDeadlineSeconds: 300
  ttlSecondsAfterFinished: 600
  template:
    metadata:
      labels:
        app.kubernetes.io/name: __APP__-backend
        app.kubernetes.io/component: backend-migration
        app.kubernetes.io/part-of: __APP__
        sunmoonai.com/app: __APP__
        sunmoonai.com/managed-by: architecture-v2
        sunmoonai.com/release-id: __RELEASE_ID__
    spec:
      restartPolicy: Never
      serviceAccountName: __APP__-backend-migration
      automountServiceAccountToken: false
      imagePullSecrets:
        - name: __IMAGE_PULL_SECRET__
      securityContext:
        runAsNonRoot: true
        runAsUser: 1001
        runAsGroup: 1001
        fsGroup: 1001
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: migration
          image: __BACKEND_IMAGE__
          imagePullPolicy: IfNotPresent
          command: ["python", "-m", "app.bootstrap.migration"]
          args: ["upgrade", "head"]
          envFrom:
            - configMapRef:
                name: __APP__-backend-config
          env:
            - name: MIGRATION_DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: MIGRATION_DATABASE_URL
            - name: DATABASE_URL
              valueFrom:
                secretKeyRef:
                  name: __APP__-backend-runtime
                  key: MIGRATION_DATABASE_URL
          resources:
            requests:
              cpu: 50m
              memory: 96Mi
            limits:
              cpu: 500m
              memory: 384Mi
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: tmp
              mountPath: /tmp
      volumes:
        - name: tmp
          emptyDir:
            sizeLimit: 64Mi
