import asyncio
import json
import logging
from io import BytesIO
from typing import Any, Dict, NamedTuple, Union

from PIL import Image
from pyppeteer.browser import Browser
from pyppeteer.launcher import Launcher
from pyppeteer.page import Page
from websockets.exceptions import ConnectionClosedError


class GenerateFailure(Exception):
    pass


class PuppeteerCardBase(NamedTuple):
    def serialize(self):
        """
        Serialize all the data included in the NamedTuple attribute
        into a dict.
        """
        raise NotImplementedError


class PuppeeterGeneratorBase(NamedTuple):
    name: str
    html_data: str
    max_width: int


class PuppeeterGenerator:
    def __init__(self, loop: asyncio.AbstractEventLoop = None) -> None:
        self._browser: Browser = None
        self._page_navigator: Dict[str, Dict[str, Union[Page, int]]] = {}
        self._page: Page = None
        self._loop = loop
        if not self._loop:
            self._loop = asyncio.get_event_loop()
        self._launcher = Launcher(
            headless=True,
            args=["--no-sandbox"],
            loop=self._loop,
            logLevel=logging.INFO,
            autoClose=False,
            handleSIGINT=False,
            handleSIGTERM=False,
            handleSIGHUP=False,
        )
        self.logger = logging.getLogger("puppeeter.PuppeeterGenerator")

    async def init(self):
        self.logger.info("Initiating the headless browser...")
        self._browser = await self._launcher.launch()
        self.logger.info("Headless browser initiated")
        # self._page = await self._browser.newPage()
        # self.logger.info("Navigating to the UserCard HTML!")
        # await self._page.goto(f"data:text/html;charset=utf-8,{HTML_PAGE}")
        self.logger.info("Card generator ready!")

    async def close(self):
        self.logger.info("Closing down browser and cleaning up...")
        if not self._launcher.chromeClosed:
            try:
                await self._launcher.killChrome()
            except (
                asyncio.exceptions.CancelledError,
                ConnectionClosedError,
                asyncio.exceptions.InvalidStateError,
            ):
                pass

    async def bind(self, pages: PuppeeterGeneratorBase):
        self.logger.info(f"Creating new page for {pages.name}")
        new_page = await self._browser.newPage()
        await new_page.goto(f"data:text/html;charset=utf-8,{pages.html_data}")
        self.logger.info(f"{pages.name} is now binded!")
        self._page_navigator[pages.name] = {
            "p": new_page,
            "mw": pages.max_width,
        }

    @staticmethod
    def _generate_expression(json_data: Any):
        dumped_data = json.dumps(json_data, ensure_ascii=False).replace("'", "\\'")
        function_value = f"seleniumCallChange('{dumped_data}')"
        wrapped_function = "() => {" + function_value + "; return '';}"
        return wrapped_function

    async def generate(self, name: str, data: PuppeteerCardBase):
        try:
            page_data = self._page_navigator[name]
        except (ValueError, KeyError, IndexError, AttributeError):
            raise GenerateFailure(f"Cannot find {name} on pages navigation list")

        real_page: Page = page_data["p"]
        max_width: int = page_data["mw"]
        self.logger.info("Evaluating expression and function...")
        generated_eval = self._generate_expression(data.serialize())
        await real_page.evaluate(generated_eval)

        dimensions = await real_page.evaluate(
            """() => {
                return {
                    width: document.body.clientWidth,
                    height: document.body.clientHeight,
                }
            }
            """
        )
        self.logger.info("Taking a screenshot of the page and cropping it...")
        screenies = await real_page.screenshot()

        im = Image.open(BytesIO(screenies))
        im = im.crop((0, 0, max_width, dimensions["height"]))
        img_byte_arr = BytesIO()
        im.save(img_byte_arr, format="PNG")
        return img_byte_arr.getvalue()
