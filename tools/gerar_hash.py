import hashlib, sys
print(hashlib.sha256(sys.argv[1].encode("utf-8")).hexdigest())
