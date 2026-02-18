import uvicorn
from loguru import logger
from pyngrok import ngrok

from app.config import config

if __name__ == "__main__":

    # Set up ngrok if enabled in the configuration
    # Terminate any existing ngrok tunnels
    ngrok.kill()

    # Set your authentication token
    # Replace "your_ngrok_auth_token" with your actual token
    ngrok.set_auth_token("2xMkJ7pPZ7UPcn6XWX7Q0QqcXFt_4fwuS547B5ePzxAdQLMhh")
    public_url = ngrok.connect(8081, bind_tls=True)
    logger.info(public_url)

    # Start the server with uvicorn
    logger.info(
        "start server, docs: http://127.0.0.1:" + str(config.listen_port) + "/docs"
    )
    uvicorn.run(
        app="app.asgi:app",
        host=config.listen_host,
        port=config.listen_port,
        reload=config.reload_debug,
        log_level="warning",
    )
