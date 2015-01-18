import urllib2
import os


class Download:
    def __init__(self, downloads):
        self._downloads = []
        for x in downloads:
            urlAndPath = x.split(";")
            if len(urlAndPath) != 2:
                raise Exception(
                    "--inauguratorDownload parameter '%s' must be a semicolon separated "
                    "tuple of url and path" % x)
            if not urlAndPath[0].startswith("http:") and not urlAndPath[0].startswith("ftp:"):
                raise Exception(
                    "--inauguratorDownload parameter '%s' must start with 'http:' or 'ftp:'" % x)
            self._downloads.append(urlAndPath)

    def download(self, destination):
        for url, path in self._downloads:
            print "Downloading '%s'" % url
            req = urllib2.urlopen(url)
            try:
                contents = req.read()
                print "Saving '%s'" % path
                fullPath = os.path.join(destination, path)
                if not os.path.isdir(os.path.dirname(fullPath)):
                    os.makedirs(os.path.dirname(fullPath))
                with open(fullPath, "wb") as f:
                    f.write(contents)
            finally:
                req.close()
