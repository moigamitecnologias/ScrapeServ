from flask import Flask, request, jsonify
import sys
import os
from dotenv import load_dotenv
import ipaddress
import socket
from urllib.parse import urlparse
import os
from worker import scrape_task, MAX_BROWSER_DIM, MIN_BROWSER_DIM, DEFAULT_BROWSER_DIM, DEFAULT_WAIT, MAX_SCREENSHOTS, MAX_WAIT, DEFAULT_SCREENSHOTS
import json
import mimetypes
import boto3


app = Flask(__name__)

"""

Flask server runs and gets requests to scrape.

The server worker process spawned by gunicorn itself maintains a separate pool of scraping workers (there should be just one server worker - see Dockerfile).

Upon a request to /scrape, the gunicorn worker asks the pool for a process to run a scrape, which spawns an isolated browser context.

The scrape workers' memory usage and number are limited by constants set in worker.py.

"""

# For optional API key
load_dotenv()  # Load in API keys
SCRAPER_API_KEYS = [value for key, value in os.environ.items() if key.startswith('SCRAPER_API_KEY')]


@app.route('/')
def home():
    return "A rollicking band of pirates we, who tired of tossing on the sea, are trying our hands at burglary, with weapons grim and gory."


def is_private_ip(ip_str: str) -> bool:
    """
    Checks if the given IP address string (e.g., '10.0.0.1', '127.0.0.1')
    is private, loopback, or link-local.
    """
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return (
            ip_obj.is_loopback or
            ip_obj.is_private or
            ip_obj.is_reserved or
            ip_obj.is_link_local or
            ip_obj.is_multicast
        )
    except ValueError:
        return True  # If it can't parse, treat as "potentially unsafe"


def url_is_safe(url: str, allowed_schemes=None) -> bool:
    if allowed_schemes is None:
        # By default, let's only allow http(s)
        allowed_schemes = {"http", "https"}

    # Parse the URL
    parsed = urlparse(url.strip())
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.split(':')[0]  # extract host portion w/o port
    if scheme not in allowed_schemes:
        print(f"URL blocked: scheme '{scheme}' is not allowed.", file=sys.stderr)
        return False

    try:
        # Resolve the domain name to IP addresses
        # This can raise socket.gaierror if domain does not exist
        addrs = socket.getaddrinfo(netloc, None)
    except socket.gaierror:
        print(f"URL blocked: cannot resolve domain {netloc}", file=sys.stderr)
        return False

    # Check each resolved address
    for addrinfo in addrs:
        ip_str = addrinfo[4][0]
        if is_private_ip(ip_str):
            print(f"URL blocked: IP {ip_str} for domain {netloc} is private/loopback/link-local.", file=sys.stderr)
            return False

    # If all resolved IPs appear safe, pass it
    return True


# Includes dot
def get_ext_from_content_type(content_type: str):
    mime_type = content_type.split(';')[0].strip()
    extensions = mimetypes.guess_all_extensions(mime_type)
    if len(extensions):
        return f"{extensions[0]}"
    return ""


@app.route('/scrape', methods=('POST',))
def scrape():
    if len(SCRAPER_API_KEYS):
        auth_header = request.headers.get('Authorization')
        if auth_header is None:
            return jsonify({"error": "Authorization header is missing"}), 401

        if not auth_header.startswith('Bearer '):
            return jsonify({"error": "Invalid authorization header format"}), 401

        user_key = auth_header.split(' ')[1]
        if user_key not in SCRAPER_API_KEYS:
            return jsonify({'error': 'Invalid API key'}), 401

    url = request.json.get('url')

    if not url:
        return jsonify({'error': 'No URL provided'}), 400
    if not url_is_safe(url):
        return jsonify({'error': 'URL was judged to be unsafe'}), 400

    wait = request.json.get('wait', DEFAULT_WAIT)
    n_screenshots = request.json.get('max_screenshots', DEFAULT_SCREENSHOTS)
    browser_dim = request.json.get('browser_dim', DEFAULT_BROWSER_DIM)

    if wait < 0 or wait > MAX_WAIT:
        return jsonify({
            'error': f'Value {wait} for "wait" is unacceptable; must be between 0 and {MAX_WAIT}'
        }), 400
    
    for i, name in enumerate(['width', 'height']):
        if browser_dim[i] > MAX_BROWSER_DIM[i] or browser_dim[i] < MIN_BROWSER_DIM[i]:
            return jsonify({
                'error': f'Value {browser_dim[i]} for browser {name} is unacceptable; must be between {MIN_BROWSER_DIM[i]} and {MAX_BROWSER_DIM[i]}'
            }), 400
        
    if n_screenshots > MAX_SCREENSHOTS:
        return jsonify({
                'error': f'Value {n_screenshots} for max_screenshots is unacceptable; must be below {MAX_SCREENSHOTS}'
            }), 400
    
    # Determine the image format from the Accept header
    accept_header = request.headers.get('Accept', 'image/jpeg')
    accepted_formats = {
        'image/webp': 'webp',
        'image/png': 'png',
        'image/jpeg': 'jpeg',
        'image/*': 'jpeg',
        '*/*': 'jpeg'
    }

    image_format = accepted_formats.get(accept_header)
    if not image_format:
        accepted_formats_list = ', '.join(accepted_formats.keys())
        return jsonify({
            'error': f'Unsupported image format in Accept header ({accept_header}). Supported Accept header values are: {accepted_formats_list}'
        }), 406

    content_file = None
    try:
        status, headers, content_file, screenshot_files, metadata = scrape_task.apply_async(
            args=[url, wait, image_format, n_screenshots, browser_dim], kwargs={}
        ).get(timeout=60)  # 60 seconds
        headers = {str(k).lower(): v for k, v in headers.items()}  # make headers all lowercase (they're case insensitive)
    except Exception as e:
        # If scrape_in_child uses too much memory, it seems to end up here.
        # however, if exit(0) is called, I find it doesn't.
        print(f"Exception raised from scraping process: {e}", file=sys.stderr, flush=True)

    successful = True if content_file else False

    if successful:
        try:
            # 1. Obtenha o nome do seu bucket S3 de uma variável de ambiente
            bucket_name = os.getenv('S3_BUCKET_NAME')
            s3_client = boto3.client('s3')
            uploaded_urls = []

            # 2. Iterar sobre os arquivos de screenshot
            for i, ss_path in enumerate(screenshot_files):
                # Gere um nome de arquivo único para o S3
                import uuid
                object_name = f"screenshots/{uuid.uuid4()}.png"
                
                # Faça o upload do arquivo para o S3
                s3_client.upload_file(ss_path, bucket_name, object_name)
                
                # Construa a URL do objeto e adicione à lista
                location = s3_client.get_bucket_location(Bucket=bucket_name)['LocationConstraint']
                url = f"https://{bucket_name}.s3.{location}.amazonaws.com/{object_name}"
                uploaded_urls.append(url)

                # Apague o arquivo temporário localmente
                os.remove(ss_path)

            # 3. Retorne uma resposta JSON com as URLs
            return jsonify({
                "success": True,
                "screenshot_urls": uploaded_urls,
                "metadata": metadata
            }), 200

        except Exception as e:
            print(f"Erro ao fazer upload ou retornar URLs: {e}", file=sys.stderr, flush=True)
            return jsonify({
                'error': 'Erro no upload para o S3 ou na resposta da API.'
            }), 500

    else:
        return jsonify({
            'error': "This is a generic error message; sorry about that."
        }), 500
