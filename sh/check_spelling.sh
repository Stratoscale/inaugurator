#/bin/sh
if grep inugurator -i -r . | grep -v check_spelling; then
    echo "misspeling found"
    exit 1
fi
exit 0
