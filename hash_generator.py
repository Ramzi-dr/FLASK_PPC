import bcrypt


def hash_generator(to_hash):
    return bcrypt.hashpw(to_hash.encode(), bcrypt.gensalt()).decode()
    
    
user = "AdmiHS"
password = "Security@5!"
super_password ="Super@Home15!"



print(hash_generator(to_hash=super_password))



