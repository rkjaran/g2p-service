# Simple Flask wrapper for the Sequitur grapheme-to-phoneme library.

## Steps

### Build Docker image

    docker build -t g2p-service .
    
### Run service
Train, or somehow acquire a Sequitur G2P model expose it to the container as
`/app/final.mdl`

    docker run -p 8000:8000 -v <path-to-model>:/app/final.mdl g2p-service
