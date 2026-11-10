from django.apps import AppConfig

class DrlAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'drl_app'

    def ready(self):
        import os
        if os.environ.get('RUN_MAIN') == 'true':
            import threading
            import time
            def warmup():
                time.sleep(3)
                try:
                    os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'
                    from deepface import DeepFace
                    DeepFace.build_model("Facenet")
                except Exception:
                    pass
            threading.Thread(target=warmup, daemon=True).start()
