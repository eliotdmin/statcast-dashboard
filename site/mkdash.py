import json, os
# Where the pipeline writes its JSON. Defaults to the repo's own output/,
# which is what you want when running this from a checkout.
OUTDIR = os.environ.get("STATCAST_OUT", "output") + "/"
UP = OUTDIR
raw = json.load(open(UP + "blocks_all.json"))
for k in ("bat", "pit"):
    bi = {b: i for i, b in enumerate(raw[k]["blocks"])}
    for r in raw[k]["rows"]:
        r["b"] = {str(bi[b]): [round(x, 1) for x in v] for b, v in r["b"].items()}
D = json.dumps(raw, separators=(",", ":"))
print("payload bytes:", len(D))

HEAD = open("head.html").read()
BODY = open("body.html").read()
out = HEAD + BODY.replace("__DATA__", D)
open("stretch_finder.html", "w").write(out)
print("wrote", os.path.getsize("stretch_finder.html"))
