def number_to_bangla_words(n):
    """
    Convert integer number to Bangla words
    Example: 50 -> পঞ্চাশ
    """

    bn_units = [
        "", "এক", "দুই", "তিন", "চার", "পাঁচ",
        "ছয়", "সাত", "আট", "নয়"
    ]

    bn_teens = [
        "দশ", "এগারো", "বারো", "তেরো", "চৌদ্দ",
        "পনেরো", "ষোল", "সতেরো", "আঠারো", "উনিশ"
    ]

    bn_tens = [
        "", "", "বিশ", "ত্রিশ", "চল্লিশ",
        "পঞ্চাশ", "ষাট", "সত্তর", "আশি", "নব্বই"
    ]

    def two_digit(num):
        if num < 10:
            return bn_units[num]
        elif 10 <= num < 20:
            return bn_teens[num - 10]
        else:
            t = num // 10
            u = num % 10
            return bn_tens[t] + (" " + bn_units[u] if u else "")

    def three_digit(num):
        h = num // 100
        r = num % 100

        if h == 0:
            return two_digit(r)
        elif r == 0:
            return bn_units[h] + " শত"
        else:
            return bn_units[h] + " শত " + two_digit(r)

    if n == 0:
        return "শূন্য"

    if n < 0:
        return "ঋণ " + number_to_bangla_words(abs(n))

    parts = []

    crore = n // 10000000
    n %= 10000000

    lakh = n // 100000
    n %= 100000

    thousand = n // 1000
    n %= 1000

    if crore:
        parts.append(two_digit(crore) + " কোটি")

    if lakh:
        parts.append(two_digit(lakh) + " লাখ")

    if thousand:
        parts.append(two_digit(thousand) + " হাজার")

    if n:
        parts.append(three_digit(n))

    return " ".join(parts).strip()

print(number_to_bangla_words(77))