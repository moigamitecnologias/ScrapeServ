
## Deploying onto Docker Hub

Using docker buildx to build for different platforms

Made new builder instance with the name `scraperbuilder` like below:

### First Time

```
# Create a new builder instance
docker buildx create --name scraperbuilder --use

# Verify the builder is working
docker buildx inspect --bootstrap

# Login
docker login
```

### Build and Push

```
docker buildx build --platform linux/amd64,linux/arm64 \
  -t usaiinc/scraper:latest \
  -f scraper/Dockerfile \
  --push \
  .
```
