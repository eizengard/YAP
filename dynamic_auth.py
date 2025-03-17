# Store in the same directory as your app.py

# Dynamic.xyz Configuration
DYNAMIC_ENVIRONMENT_ID = "d94a84a6-f513-4f6a-9dde-93a45211d50e"
DYNAMIC_PUBLIC_KEY = """-----BEGIN PUBLIC KEY-----
MIICIjANBgkqhkiG9w0BAQEFAAOCAg8AMIICCgKCAgEA03f5Vo7Dj9thm9huEuvB
XKNmZL0Do8rF/K4/42P+Vj6Awg53B7YG8X4mQ9I76Rw5lIn+rAfyhOVz893ZI23K
GPhmGa+93tQ7HcuqTLV03Z9GzcwEaSAWh5avSLvfVkQvFITZFXbni1/UYGNMrvJv
idMGAkg0fqgxkhUixt72mdKvvdJeR43JmdACoF2NK513X+DGMwY3MJlN9ZvVkCMk
ceHgjKTEF3OMHFF+ojmEOkGVE64RAYnOQHyHC7XWjh9bg0DBHky6SlwMTR4VE+5p
dAvgt2iHo/XgGEqca8TntyWZtSSQ1pZlcZxoK2ufHxE3X9JZ68WFPkYVf6/lHFIO
F7tIDEEhccdbXewOTt3SIoNAr7cdpsoUDB+2EqSIwPh0jv4rhRM1SSmH5a7F5jqq
o03Lc50ra2UevuHQKALtuodJvMZMIZVf79DTx3YA5XDLYdAXJV1kwgOEEZkiX0Ud
14na0lw6bpXyQVDZHzPg2q4dKqfFp+YOCXVCxKY9FjnRkmezM1Dea7wuewh/WWtB
TTNhcMipqqZJyzlb40aY3JTsvOJnOoRauxDl/5E+x7cyPecT9RR4fwfIr5HRKqyf
sdxhm5GAGFAez6tgvtcsCi/MyS+C60Zu6Sc5hPSifpqPBCzq+sLlE5XXlfCvp88B
9/dx94UhXv4UIeeBgCGtj5sCAwEAAQ==
-----END PUBLIC KEY-----"""

DYNAMIC_JWKS_URL = "https://app.dynamic.xyz/api/v0/sdk/d94a84a6-f513-4f6a-9dde-93a45211d50e/.well-known/jwks"

# Function to verify Dynamic JWT tokens
def verify_dynamic_jwt(token):
    from jose import jwt
    try:
        # Decode and verify the JWT using the public key
        decoded = jwt.decode(
            token,
            DYNAMIC_PUBLIC_KEY,
            algorithms=['RS256'],
            audience=DYNAMIC_ENVIRONMENT_ID
        )
        return decoded
    except Exception as e:
        print(f"JWT verification error: {str(e)}")
        return None 