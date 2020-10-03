import re
import pandas as pd
import pyppeteer
import time

from pathlib import Path
from requests_html import HTMLSession
from tinydb import TinyDB

S = HTMLSession()
db = TinyDB("rooms.json")

URL = "https://www.airbnb.co.in/rooms/{}"
latlng = re.compile(r"\d+\.\d+")
criteria = ["Cleanliness", "Communication", "Check-in", "Accuracy", "Location", "Value"]


def get_page(id):
    print("In page")
    r = S.get(URL.format(id))
    print("Get URL done.")
    r.html.render(retries=1, scrolldown=8, sleep=2)
    print("Render done.")
    return r


def extract_reviews(page):
    d = {}

    reviews = page.html.find('div[data-section-id="REVIEWS_DEFAULT"] ._1s11ltsf')
    if len(reviews):
        for review in reviews:
            criterion, score = review.text.split("\n")
            d[criterion] = score
    else:
        for criterion in criteria:
            d[criterion] = "NA"

    return d


def extract_lat_lng(page):
    d = {}

    try:
        address = (
            page.html.find('div[data-veloute="map/GoogleMap"]', first=True)
            .find('a[href^="https://maps.google.com/maps"]', first=True)
            .attrs["href"]
        )
        d["lat"], d["lng"] = re.findall(latlng, address)
    except AttributeError:
        d["lat"], d["lng"] = "NA", "NA"

    return d


def process(page):
    d = {"target": page.html.url.rsplit("/", 1)[1]}

    d.update(extract_reviews(page))
    d.update(extract_lat_lng(page))
    return d


if __name__ == "__main__":
    cached = {int(d["target"]) for d in db.all()}
    print(f"Cached rooms: {cached}")

    properties_df = pd.read_csv("airbnb-goa.csv")
    for idx, property in properties_df.iterrows():
        target = property["target"]
        if target not in cached:
            print(f"Processing {target}")
            try:
                page = get_page(target)
                db.insert(process(page))
            except pyppeteer.errors.TimeoutError:
                continue
