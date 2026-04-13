from app import create_app
import os

app = create_app(start_scheduler=False)

if __name__ == "__main__":
    from app.scheduler import start_scheduler

    app.config["ENABLE_INTERNAL_SCHEDULER"] = True
    start_scheduler(app)

    # Get port from environment variable (Railway provides this)
    port = int(os.environ.get("PORT", 5000))
    # host='0.0.0.0' makes it accessible on network
    app.run(host='0.0.0.0', port=port, debug=False)
