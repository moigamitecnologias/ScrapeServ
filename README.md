# Simple URL 🌐 to Screenshots 📷 API

You run the API on your machine, you send it a URL, and you get back the website data as a file plus screenshots of the site. Simple as.

This project was made to support [Abbey](https://github.com/US-Artificial-Intelligence/abbey), an AI platform. Its author is [Gordon Kamer](https://x.com/gkamer8).

Some highlights:
- Scrolls through the page and takes screenshots of different sections
- Runs in a docker container
- Browser-based (will run websites' Javascript)
- Gives you the HTTP status code and headers from the first request
- Automatically handles 302 redirects
- Handles download links properly
- Tasks are processed in a queue with configurable memory allocation
- Blocking API
- Zero state or other complexity

This web scraper is resource intensive but higher quality than many alternatives. Websites are scraped using Playwright, which launches a Firefox browser context for each job.

## Setup

You should have Docker and `docker compose` installed.

1. Clone this repo
2. Run `docker compose up` (a `docker-compose.yml` file is provided for your use)

...and the service will be available at `http://localhost:5006`. See the Usage section below for details on how to interact with it.

### API Keys

You may set an API key using a `.env` file inside the `/scraper` folder (same level as `app.py`).

You can set as many API keys as you'd like; allowed API keys are those that start with `SCRAPER_API_KEY`. For example, here is a `.env` file that has three available keys:

```
SCRAPER_API_KEY=should-be-secret
SCRAPER_API_KEY_OTHER=can-also-be-used
SCRAPER_API_KEY_3=works-too
```

API keys are sent to the service using the Authorization Bearer scheme.

## Usage

The root path `/` returns status 200 if online, plus some Gilbert and Sullivan lyrics (you can go there in your browser to see if it's online).

The only other path is `/scrape`, to which you send a JSON formatted POST request and (if all things go well) receive a `multipart/mixed` type response.

The response will be either:

- Status 200: m`ultipart/mixed` response where the first part is type `application/json` with information about the request; the second part is the website data (usually `text/html`); and the remaining parts are up to 5 screenshots.
- Not status 200: `application/json` response with an error message under the "error" key.

Here's a sample cURL request:

```
curl -X POST "http://localhost:5006/scrape"
    -H "Content-Type: application/json"
    -d '{"url": "https://us.ai"}'
```

Here is a code example using Python and the requests_toolbelt library to let you interact with the API properly:

```
import requests
from requests_toolbelt.multipart.decoder import MultipartDecoder
import sys

data = {
    'url': "https://us.ai"
}
# Optional if you're using an API key
headers = {
    'Authorization': f'Bearer Your-API-Key'
}

response = requests.post('http://localhost:5006/scrape', json=data, headers=headers, timeout=30)

if response.status !== 200:
    my_json = response.json()
    message = my_json['error']
    print(f"Error scraping: {message}", file=sys.stderr)
else:
    decoder = MultipartDecoder.from_response(response)
    resp = None
    for i, part in enumerate(decoder.parts):
        if i == 0:  # First is some JSON
            json_part = json.loads(part.content)
            req_status = json_part['status']  # An integer
            req_headers = json_part['headers']  # Headers from the request made to your URL
            metadata = json_part['metadata']  # Information like the number of screenshots and their compressed / uncompressed sizes
            # ...
        elif i == 1:  # Next is the actual content of the page
            content = part.content
            headers = part.headers
            # ...
        else:  # Other parts are screenshots, if they exist
            img = part.content
            headers = part.headers
            # ...
```

## Security Considerations

Navigating to untrusted websites is a serious security problem. Risks are somewhat mitigated in the following ways:

- Runs as isolated container (container isolation)
- Each website is scraped in a new browser context (process isolation)
- Strict memory limits and timeouts for each task
- Checks the URL to make sure that it's not too weird (loopback, non http, etc.)

You may take additional precautions depending on your needs, like:

- Only giving the API trusted URLs (or otherwise screening URLs)
- Running this API on isolated VMs (hardware isolation)
- Using one API instance per user
- Not making any secret files or keys available inside the container (besides the API key for the scraper itself)

**If you'd like to make sure that this API is up to your security standards, please examine the code and open issues! It's not a big repo.**

## Other Configuration

You can control memory limits and other variables at the top of `scraper/worker.py`. Here are the defaults:

```
MEM_LIMIT_MB = 4_000  # 4 GB memory threshold for child scraping process
MAX_SCREENSHOTS = 5
SCREENSHOT_JPEG_QUALITY = 85
BROWSER_HEIGHT = 2000
BROWSER_WIDTH = 1280
```
