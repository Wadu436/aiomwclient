import time

import aiomwclient.errors
import aiomwclient.listing
from aiomwclient.util import parse_timestamp


class Page(object):
    async def init(self, site, name, info=None, extra_properties=None) -> "Page":
        if type(name) is type(self):
            self.__dict__.update(name.__dict__)
            return
        self.site = site
        self.name = name
        self._textcache = {}

        if not info:
            if extra_properties:
                prop = "info|" + "|".join(iter(extra_properties.keys()))
                extra_props = []
                for extra_prop in iter(extra_properties.values()):
                    extra_props.extend(extra_prop)
            else:
                prop = "info"
                extra_props = ()

            if type(name) is int:
                info = await self.site.get(
                    "query", prop=prop, pageids=name, inprop="protection", *extra_props
                )
            else:
                info = await self.site.get(
                    "query", prop=prop, titles=name, inprop="protection", *extra_props
                )
            info = next(iter(info["query"]["pages"].values()))
        self._info = info

        if "invalid" in info:
            raise aiomwclient.errors.InvalidPageTitle(info.get("invalidreason"))

        self.namespace = info.get("ns", 0)
        self.name = info.get("title", u"")
        if self.namespace:
            self.page_title = self.strip_namespace(self.name)
        else:
            self.page_title = self.name

        self.base_title = self.page_title.split("/")[0]
        self.base_name = self.name.split("/")[0]

        self.touched = parse_timestamp(info.get("touched"))
        self.revision = info.get("lastrevid", 0)
        self.exists = "missing" not in info
        self.length = info.get("length")
        self.protection = {
            i["type"]: (i["level"], i["expiry"])
            for i in info.get("protection", ())
            if i
        }
        self.redirect = "redirect" in info
        self.pageid = info.get("pageid", None)
        self.contentmodel = info.get("contentmodel", None)
        self.pagelanguage = info.get("pagelanguage", None)
        self.restrictiontypes = info.get("restrictiontypes", None)

        self.last_rev_time = None
        self.edit_time = None

        return self

    async def redirects_to(self):
        """ Get the redirect target page, or None if the page is not a redirect."""
        info = await self.site.get(
            "query", prop="pageprops", titles=self.name, redirects=""
        )
        if "redirects" in info["query"]:
            for page in info["query"]["redirects"]:
                if page["from"] == self.name:
                    return Page(self.site, page["to"])
            return None
        else:
            return None

    async def resolve_redirect(self):
        """ Get the redirect target page, or the current page if its not a redirect."""
        target_page = await self.redirects_to()
        if target_page is None:
            return self
        else:
            return target_page

    def __repr__(self):
        return "<Page object '%s' for %s>" % (self.name.encode("utf-8"), self.site)

    def __unicode__(self):
        return self.name

    @staticmethod
    def strip_namespace(title):
        if title[0] == ":":
            title = title[1:]
        return title[title.find(":") + 1 :]

    @staticmethod
    def normalize_title(title):
        # TODO: Make site dependent
        title = title.strip()
        if title[0] == ":":
            title = title[1:]
        title = title[0].upper() + title[1:]
        title = title.replace(" ", "_")
        return title

    def can(self, action):
        """Check if the current user has the right to carry out some action
        with the current page.

        Example:
            >>> page.can('edit')
            True

        """
        level = self.protection.get(action, (action,))[0]
        if level == "sysop":
            level = "editprotected"

        return level in self.site.rights

    async def get_token(self, type, force=False):
        return await self.site.get_token(type, force, title=self.name)

    async def text(self, section=None, expandtemplates=False, cache=True, slot="main"):
        """Get the current wikitext of the page, or of a specific section.

        If the page does not exist, an empty string is returned. By
        default, results will be cached and if you call text() again
        with the same section and expandtemplates the result will come
        from the cache. The cache is stored on the instance, so it
        lives as long as the instance does.

        Args:
            section (int): Section number, to only get text from a single section.
            expandtemplates (bool): Expand templates (default: `False`)
            cache (bool): Use in-memory caching (default: `True`)
        """

        if not self.can("read"):
            raise aiomwclient.errors.InsufficientPermission(self)
        if not self.exists:
            return u""
        if section is not None:
            section = str(section)

        key = hash((section, expandtemplates))
        if cache and key in self._textcache:
            return self._textcache[key]

        revs = self.revisions(
            prop="content|timestamp", limit=1, section=section, slots=slot
        )
        try:
            rev = await revs.__anext__()
            if "slots" in rev:
                text = rev["slots"][slot]["*"]
            else:
                text = rev["*"]
            self.last_rev_time = rev["timestamp"]
        except StopIteration:
            text = u""
            self.last_rev_time = None
        if not expandtemplates:
            self.edit_time = time.gmtime()
        else:
            # The 'rvexpandtemplates' option was removed in MediaWiki 1.32, so we have to
            # make an extra API call, see https://github.com/mwclient/mwclient/issues/214
            text = self.site.expandtemplates(text)

        if cache:
            self._textcache[key] = text
        return text

    async def save(self, *args, **kwargs):
        """Alias for edit, for maintaining backwards compatibility."""
        return await self.edit(*args, **kwargs)

    async def edit(
        self, text, summary=u"", minor=False, bot=True, section=None, **kwargs
    ):
        """Update the text of a section or the whole page by performing an edit operation."""
        return await self._edit(summary, minor, bot, section, text=text, **kwargs)

    async def append(
        self, text, summary=u"", minor=False, bot=True, section=None, **kwargs
    ):
        """Append text to a section or the whole page by performing an edit operation."""
        return await self._edit(summary, minor, bot, section, appendtext=text, **kwargs)

    async def prepend(
        self, text, summary=u"", minor=False, bot=True, section=None, **kwargs
    ):
        """Prepend text to a section or the whole page by performing an edit operation."""
        return await self._edit(
            summary, minor, bot, section, prependtext=text, **kwargs
        )

    async def _edit(self, summary, minor, bot, section, **kwargs):
        if not self.site.logged_in and self.site.force_login:
            raise aiomwclient.errors.AssertUserFailedError()
        if self.site.blocked:
            raise aiomwclient.errors.UserBlocked(self.site.blocked)
        if not self.can("edit"):
            raise aiomwclient.errors.ProtectedPageError(self)

        if not self.site.writeapi:
            raise aiomwclient.errors.NoWriteApi(self)

        data = {}
        if minor:
            data["minor"] = "1"
        if not minor:
            data["notminor"] = "1"
        if self.last_rev_time:
            data["basetimestamp"] = time.strftime("%Y%m%d%H%M%S", self.last_rev_time)
        if self.edit_time:
            data["starttimestamp"] = time.strftime("%Y%m%d%H%M%S", self.edit_time)
        if bot:
            data["bot"] = "1"
        if section is not None:
            data["section"] = section

        data.update(kwargs)

        if self.site.force_login:
            data["assert"] = "user"

        async def do_edit():
            result = await self.site.post(
                "edit",
                title=self.name,
                summary=summary,
                token=await self.get_token("edit"),
                **data
            )
            if result["edit"].get("result").lower() == "failure":
                raise aiomwclient.errors.EditError(self, result["edit"])
            return result

        try:
            result = await do_edit()
        except aiomwclient.errors.APIError as e:
            if e.code == "badtoken":
                # Retry, but only once to avoid an infinite loop
                await self.get_token("edit", force=True)
                try:
                    result = await do_edit()
                except aiomwclient.errors.APIError as e:
                    self.handle_edit_error(e, summary)
            else:
                self.handle_edit_error(e, summary)

        # 'newtimestamp' is not included if no change was made
        if "newtimestamp" in result["edit"].keys():
            self.last_rev_time = parse_timestamp(result["edit"].get("newtimestamp"))

        # Workaround for https://phabricator.wikimedia.org/T211233
        # for cookie in self.site.connection.cookies:
        new_cookies = []
        for cookie in self.site.connection.cookie_jar:
            if "PostEditRevision" in cookie.key:
                # Delete cookie (https://github.com/aio-libs/aiohttp/issues/4942)
                cookie["max-age"] = -1
                new_cookies.append((cookie.key, cookie))
        self.site.connection.cookie_jar.update_cookies(new_cookies)

        # clear the page text cache
        self._textcache = {}
        return result["edit"]

    def handle_edit_error(self, e, summary):
        if e.code == "editconflict":
            raise aiomwclient.errors.EditError(self, summary, e.info)
        elif e.code in {
            "protectedtitle",
            "cantcreate",
            "cantcreate-anon",
            "noimageredirect-anon",
            "noimageredirect",
            "noedit-anon",
            "noedit",
            "protectedpage",
            "cascadeprotected",
            "customcssjsprotected",
            "protectednamespace-interface",
            "protectednamespace",
        }:
            raise aiomwclient.errors.ProtectedPageError(self, e.code, e.info)
        elif e.code == "assertuserfailed":
            raise aiomwclient.errors.AssertUserFailedError()
        else:
            raise e

    async def touch(self):
        """Perform a "null edit" on the page to update the wiki's cached data of it.
        This is useful in contrast to purge when needing to update stored data on a wiki,
        for example Semantic MediaWiki properties or Cargo table values, since purge
        only forces update of a page's displayed values and not its store.
        """
        if not self.exists:
            return
        await self.append("")

    async def move(self, new_title, reason="", move_talk=True, no_redirect=False):
        """Move (rename) page to new_title.

        If user account is an administrator, specify no_redirect as True to not
        leave a redirect.

        If user does not have permission to move page, an InsufficientPermission
        exception is raised.

        """
        if not self.can("move"):
            raise aiomwclient.errors.InsufficientPermission(self)

        if not self.site.writeapi:
            raise aiomwclient.errors.NoWriteApi(self)

        data = {}
        if move_talk:
            data["movetalk"] = "1"
        if no_redirect:
            data["noredirect"] = "1"
        result = await self.site.post(
            "move",
            ("from", self.name),
            to=new_title,
            token=await self.get_token("move"),
            reason=reason,
            **data
        )
        return result["move"]

    async def delete(self, reason="", watch=False, unwatch=False, oldimage=False):
        """Delete page.

        If user does not have permission to delete page, an InsufficientPermission
        exception is raised.

        """
        if not self.can("delete"):
            raise aiomwclient.errors.InsufficientPermission(self)

        if not self.site.writeapi:
            raise aiomwclient.errors.NoWriteApi(self)

        data = {}
        if watch:
            data["watch"] = "1"
        if unwatch:
            data["unwatch"] = "1"
        if oldimage:
            data["oldimage"] = oldimage
        result = await self.site.post(
            "delete",
            title=self.name,
            token=await self.get_token("delete"),
            reason=reason,
            **data
        )
        return result["delete"]

    async def purge(self):
        """Purge server-side cache of page. This will re-render templates and other
        dynamic content.

        """
        await self.site.post("purge", titles=self.name)

    # def watch: requires 1.14

    # Properties
    def backlinks(
        self,
        namespace=None,
        filterredir="all",
        redirect=False,
        limit=None,
        generator=True,
    ):
        """List pages that link to the current page, similar to Special:Whatlinkshere.

        API doc: https://www.mediawiki.org/wiki/API:Backlinks

        """
        prefix = aiomwclient.listing.List.get_prefix("bl", generator)
        kwargs = dict(
            aiomwclient.listing.List.generate_kwargs(
                prefix,
                namespace=namespace,
                filterredir=filterredir,
            )
        )
        if redirect:
            kwargs["%sredirect" % prefix] = "1"
        kwargs[prefix + "title"] = self.name

        return aiomwclient.listing.List.get_list(generator)(
            self.site, "backlinks", "bl", limit=limit, return_values="title", **kwargs
        )

    def categories(self, generator=True, show=None):
        """List categories used on the current page.

        API doc: https://www.mediawiki.org/wiki/API:Categories

        Args:
            generator (bool): Return generator (Default: True)
            show (str): Set to 'hidden' to only return hidden categories
                or '!hidden' to only return non-hidden ones.

        Returns:
            aiomwclient.listings.PagePropertyGenerator
        """
        prefix = aiomwclient.listing.List.get_prefix("cl", generator)
        kwargs = dict(aiomwclient.listing.List.generate_kwargs(prefix, show=show))

        if generator:
            return aiomwclient.listing.PagePropertyGenerator(
                self, "categories", "cl", **kwargs
            )
        else:
            # TODO: return sortkey if wanted
            return aiomwclient.listing.PageProperty(
                self, "categories", "cl", return_values="title", **kwargs
            )

    def embeddedin(self, namespace=None, filterredir="all", limit=None, generator=True):
        """List pages that transclude the current page.

        API doc: https://www.mediawiki.org/wiki/API:Embeddedin

        Args:
            namespace (int): Restricts search to a given namespace (Default: None)
            filterredir (str): How to filter redirects, either 'all' (default),
                'redirects' or 'nonredirects'.
            limit (int): Maximum amount of pages to return per request
            generator (bool): Return generator (Default: True)

        Returns:
            aiomwclient.listings.List: Page iterator
        """
        prefix = aiomwclient.listing.List.get_prefix("ei", generator)
        kwargs = dict(
            aiomwclient.listing.List.generate_kwargs(
                prefix, namespace=namespace, filterredir=filterredir
            )
        )
        kwargs[prefix + "title"] = self.name

        return aiomwclient.listing.List.get_list(generator)(
            self.site, "embeddedin", "ei", limit=limit, return_values="title", **kwargs
        )

    def extlinks(self):
        """List external links from the current page.

        API doc: https://www.mediawiki.org/wiki/API:Extlinks

        """
        return aiomwclient.listing.PageProperty(
            self, "extlinks", "el", return_values="*"
        )

    def images(self, generator=True):
        """List files/images embedded in the current page.

        API doc: https://www.mediawiki.org/wiki/API:Images

        """
        if generator:
            return aiomwclient.listing.PagePropertyGenerator(self, "images", "")
        else:
            return aiomwclient.listing.PageProperty(
                self, "images", "", return_values="title"
            )

    def iwlinks(self):
        """List interwiki links from the current page.

        API doc: https://www.mediawiki.org/wiki/API:Iwlinks

        """
        return aiomwclient.listing.PageProperty(
            self, "iwlinks", "iw", return_values=("prefix", "*")
        )

    def langlinks(self, **kwargs):
        """List interlanguage links from the current page.

        API doc: https://www.mediawiki.org/wiki/API:Langlinks

        """
        return aiomwclient.listing.PageProperty(
            self, "langlinks", "ll", return_values=("lang", "*"), **kwargs
        )

    def links(self, namespace=None, generator=True, redirects=False):
        """List links to other pages from the current page.

        API doc: https://www.mediawiki.org/wiki/API:Links

        """
        prefix = aiomwclient.listing.List.get_prefix("pl", generator)
        kwargs = dict(
            aiomwclient.listing.List.generate_kwargs(prefix, namespace=namespace)
        )

        if redirects:
            kwargs["redirects"] = "1"
        if generator:
            return aiomwclient.listing.PagePropertyGenerator(
                self, "links", "pl", **kwargs
            )
        else:
            return aiomwclient.listing.PageProperty(
                self, "links", "pl", return_values="title", **kwargs
            )

    def revisions(
        self,
        startid=None,
        endid=None,
        start=None,
        end=None,
        dir="older",
        user=None,
        excludeuser=None,
        limit=50,
        prop="ids|timestamp|flags|comment|user",
        expandtemplates=False,
        section=None,
        diffto=None,
        slots=None,
        uselang=None,
    ):
        """List revisions of the current page.

        API doc: https://www.mediawiki.org/wiki/API:Revisions

        Args:
            startid (int): Revision ID to start listing from.
            endid (int): Revision ID to stop listing at.
            start (str): Timestamp to start listing from.
            end (str): Timestamp to end listing at.
            dir (str): Direction to list in: 'older' (default) or 'newer'.
            user (str): Only list revisions made by this user.
            excludeuser (str): Exclude revisions made by this user.
            limit (int): The maximum number of revisions to return per request.
            prop (str): Which properties to get for each revision,
                default: 'ids|timestamp|flags|comment|user'
            expandtemplates (bool): Expand templates in rvprop=content output
            section (int): Section number. If rvprop=content is set, only the contents
                of this section will be retrieved.
            diffto (str): Revision ID to diff each revision to. Use "prev", "next" and
                "cur" for the previous, next and current revision respectively.
            slots (str): The content slot (Mediawiki >= 1.32) to retrieve content from.
            uselang (str): Language to use for parsed edit comments and other localized
                messages.

        Returns:
            aiomwclient.listings.List: Revision iterator
        """
        kwargs = dict(
            aiomwclient.listing.List.generate_kwargs(
                "rv",
                startid=startid,
                endid=endid,
                start=start,
                end=end,
                user=user,
                excludeuser=excludeuser,
                diffto=diffto,
                slots=slots,
            )
        )

        if self.site.version[:2] < (1, 32) and "rvslots" in kwargs:
            # https://github.com/mwclient/mwclient/issues/199
            del kwargs["rvslots"]

        kwargs["rvdir"] = dir
        kwargs["rvprop"] = prop
        kwargs["uselang"] = uselang
        if expandtemplates:
            kwargs["rvexpandtemplates"] = "1"
        if section is not None:
            kwargs["rvsection"] = section

        return aiomwclient.listing.RevisionsIterator(
            self, "revisions", "rv", limit=limit, **kwargs
        )

    def templates(self, namespace=None, generator=True):
        """List templates used on the current page.

        API doc: https://www.mediawiki.org/wiki/API:Templates

        """
        prefix = aiomwclient.listing.List.get_prefix("tl", generator)
        kwargs = dict(
            aiomwclient.listing.List.generate_kwargs(prefix, namespace=namespace)
        )
        if generator:
            return aiomwclient.listing.PagePropertyGenerator(
                self, "templates", prefix, **kwargs
            )
        else:
            return aiomwclient.listing.PageProperty(
                self, "templates", prefix, return_values="title", **kwargs
            )
