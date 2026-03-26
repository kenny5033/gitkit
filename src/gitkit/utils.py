def gitkit_bail(assertion: bool, error_msg: str, *, okay: bool = False):
    """If assertion is True, then print the error_msg and exit. Otherwise, do nothing"""
    if assertion:
        print()
        print("Gitkit encountered an error:")
        print(error_msg)
        exit(0 if okay else 1)
