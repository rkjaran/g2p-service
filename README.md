# g2p-service

Naive Flask wrapper for
[Sequitur](https://github.com/sequitur-g2p/sequitur-g2p). Exposes a simple REST
API.

## Usage
Example service endpoint for Icelandic available at
https://nlp.talgreinir.is/pron (courtesy of [Tiro](https://tiro.is))

How do I pronounce `derp`?

    $ curl -XGET https://nlp.talgreinir.is/pron/derp | jq
    [
      {
        "results": [
          {
            "posterior": 0.9138450652404999,
            "pronunciation": "t ɛ r̥ p"
          }
        ],
        "word": "derp"
      }
    ]

Multiple word support with a POST.
    
    $ cat <<EOF | curl -XPOST -d@- https://nlp.talgreinir.is/pron | jq
    {"words": ["herp", "derp"]}
    EOF
    [
      {
        "results": [
          {
            "posterior": 0.9251423160703962,
            "pronunciation": "h ɛ r̥ p"
          }
        ],
        "word": "herp"
      },
      {
        "results": [
          {
            "posterior": 0.9138450652404999,
            "pronunciation": "t ɛ r̥ p"
          }
        ],
        "word": "derp"
      }
    ]
    
Append `?t=tsv` to get the response in the Kaldi lexicon format.

## Steps

### Build Docker image

    docker build -t g2p-service .
    
### Run service
Train, or somehow acquire a Sequitur G2P model expose it to the container as
`/app/final.mdl`

    docker run -p 8000:8000 -v <path-to-model>:/app/final.mdl g2p-service
