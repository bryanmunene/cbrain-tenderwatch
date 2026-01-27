from app import create_app
import os

app = create_app()

if __name__ == "__main__":
    # Get port from environment variable (Railway provides this)
    port = int(os.environ.get("PORT", 5000))
    # host='0.0.0.0' makes it accessible on network
    app.run(host='0.0.0.0', port=port, debug=False)
