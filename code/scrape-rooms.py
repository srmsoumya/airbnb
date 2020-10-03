import pandas as pd
import re
import time

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.firefox.options import Options

from pathlib import Path
from tinydb import TinyDB

DRIVER_PATH = "/home/srm/Downloads/geckodriver-v0.27.0-linux64/geckodriver"
latlng = re.compile(r"\d+\.\d+")


def extract_reviews(driver, url):
    """Scrape reviews for the property from the modal window.

    Input:
        driver: Selenium webdriver
        url: URL for the reviews of the property

    Return:
        [{
            user: 'John Doe',
            date: 'September 2020',
            review: '...'
        },
        ...
        ]
    """
    d = list()
    driver.get(url)
    time.sleep(5)

    # Click all the `read more...` buttons visible on the modal screen
    try:
        for button in driver.find_element_by_css_selector(
            'div[data-testid="modal-container"]'
        ).find_elements_by_css_selector("button._ejra3kg"):
            button.click()

        modal = driver.find_element_by_css_selector(
            'div[data-testid="modal-container"]'
        )
        reviews = modal.find_elements_by_css_selector("div._8rtpcxs div._1gjypya")
        for review in reviews:
            user, date = review.find_element_by_class_name("_1oy2hpi").text.split("\n")
            r = review.find_element_by_class_name("_1y6fhhr").text
            d.append({"user": user, "date": date, "review": r})
        print(f"{len(reviews)} Reviews Done.", end=" ")
    except NoSuchElementException:
        print("No reviews found.", end=" ")

    return d


def extract_images(driver, url):
    """Scarpe image URLs for the property.

    Input:
        driver: Selenium webdriver
        url: URL for the images of the property

    Return:
        {
            images: [url1, url2, ...]
        }
    """
    d = {}
    driver.get(url)
    time.sleep(5)

    d["images"] = []
    while True:
        try:
            d["images"].append(
                driver.find_element_by_css_selector("img._6tbg2q").get_attribute(
                    "data-original-uri"
                )
            )
            button = driver.find_element_by_css_selector('button[aria-label="Next"]')
            button.click()
        except NoSuchElementException:
            print(f'{len(d["images"])} Images Done.', end=" ")
            break

    return d


def extract_lat_lng(driver):
    """Scrape latitude & longitude information from the embedded google map for the property.

    Input:
        driver: Selenium webdriver

    Return:
        {
            lat: '15.072',
            lng: '17.243'
        }
    """
    d = {}

    try:
        address = (
            driver.find_element_by_css_selector('div[data-veloute="map/GoogleMap"]')
            .find_element_by_css_selector('a[href^="https://maps.google.com/maps"]')
            .get_attribute("href")
        )

        d["lat"], d["lng"] = re.findall(latlng, address)
    except NoSuchElementException:
        d["lat"], d["lng"] = "NA", "NA"

    return d


def extract_metrics(driver):
    """Scrape metrics to compute the rating for the property.

    Input:
        driver: Selenium webdriver

    Return:
        {
            Cleanliness: '5.0',
            Communication: '4.27',
            Check-in: '2.5',
            Accuracy: '4.5',
            Location: '2.5',
            Value: '4.8'
        }
    """
    d = {}

    try:
        metrics = driver.find_elements_by_css_selector(
            'div[data-section-id="REVIEWS_DEFAULT"] ._1s11ltsf'
        )
        if len(metrics) == 0:
            raise NoSuchElementException("No metrics found for this property")
        for metric in metrics:
            criterion, score = metric.text.split("\n")
            d[criterion] = score
    except NoSuchElementException:
        for criterion in [
            "Cleanliness",
            "Communication",
            "Check-in",
            "Accuracy",
            "Location",
            "Value",
        ]:
            d[criterion] = "NA"

    return d


def extract_host_profile(driver):
    """Scrape information about the property owner.

    Input:
        driver: Selenium webdriver

    Return:
        {
            host: 'Jane Doe',
            joining_date: 'Joined in November 2018',
            host_details: '...'
        }
    """
    d = {}

    try:
        profile = driver.find_element_by_css_selector(
            'div[data-section-id="HOST_PROFILE_DEFAULT"]'
        )
        d["host"], d["joining_date"] = profile.find_element_by_class_name(
            "_svr7sj"
        ).text.split("\n")
        d["host_details"] = profile.find_element_by_class_name("_1byskwn").text
    except NoSuchElementException:
        d["host"], d["joining_date"], d["host_details"] = "NA", "NA", "NA"

    return d


def extract_room_details(driver, url):
    """Scrape room related information like (lat,lng), ratings & host profile.

    Input:
        driver: Selenium webdriver
        url: URL of the property

    Return:
        {
            lat: '15.072',
            lng: '17.243',
            Cleanliness: '5.0',
            Communication: '4.27',
            Check-in: '2.5',
            Accuracy: '4.5',
            Location: '2.5',
            Value: '4.8',
            host: 'Jane Doe',
            joining_date: 'Joined in November 2018',
            host_details: '...'
        }
    """
    d = {}

    driver.get(url)
    time.sleep(5)

    # Scroll to the bottom of the page
    page_height = int(driver.execute_script("return document.body.scrollHeight"))
    page_down = 6
    buffer_height = int(page_height / page_down)

    for i in range(1, page_height, buffer_height):
        driver.execute_script(f"window.scrollTo(0, {i})")
        time.sleep(1)

    d.update(extract_lat_lng(driver))
    print("Lat,Lng Done.", end=" ")
    d.update(extract_metrics(driver))
    print("Metrics Done.", end=" ")
    d.update(extract_host_profile(driver))
    print("Host Profile Done.", end=" ")

    return d


def create_driver(driver_path):
    """Create Selenium web-driver for Firefox.

    Input:
        driver_path: Path to the Gecko driver

    Return:
        driver: web-driver
    """
    options = Options()
    options.headless = True
    driver = webdriver.Firefox(executable_path=driver_path, options=options)
    driver.maximize_window()

    return driver


def process(driver, target):
    """Combine scraped information for the room like room-details, images & reviews."""
    room = {"target": target}
    url = f"https://www.airbnb.co.in/rooms/{target}"

    room.update(extract_room_details(driver, url))
    room.update(extract_images(driver, f"{url}/photos/"))
    room["reviews"] = extract_reviews(driver, f"{url}/reviews/")

    return room


def main():
    driver = create_driver(DRIVER_PATH)
    DATA = Path("data")

    # JSON datastore
    db = TinyDB(DATA / "airbnb-goa-rooms.json")

    # cached properties
    cached = {int(d["target"]) for d in db.all()}
    print(f"Cached rooms: {cached}")

    # List of properties
    properties_df = pd.read_csv(DATA / "airbnb-goa-list.csv")

    for idx, property in properties_df.iterrows():
        target = property["target"]
        if target not in cached:  # Check if it is not already scraped
            print(f"Target: {target}", end=" ")
            room = process(driver, target)
            db.insert(room)
            print("Waiting...", end=" ")
            time.sleep(2)
            print("Done.")

    driver.close()


if __name__ == "__main__":
    main()
