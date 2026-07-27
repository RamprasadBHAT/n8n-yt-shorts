from youtube_upload import main
if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument('--queue',default='output/scripts.json'); main(**vars(ap.parse_args()))
