from io import BytesIO
from datetime import datetime, timedelta

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
except ImportError:
    plt = None
    mdates = None




def draw_all_xticks(data, title, filename=None):
    dates = []
    date_labels = []
    counts = []

    for timestamp, count in data:
        count = int(count)
        timestamp = int(timestamp / 1000)
        dt_obj = datetime.fromtimestamp(int(timestamp))
        dates.append(dt_obj)
        date_labels.append(dt_obj.strftime('%Y-%m-%d %H:%M'))
        counts.append(count)

    fig, ax = plt.subplots()
    fig.set_figwidth(32)
    fig.set_figheight(8)
    ax.plot(dates, counts, 'o-')

    format_str = mdates.DateFormatter('%Y-%m-%d %H:%M')
    ax.xaxis.set_major_formatter(format_str)

    # Customize x-axis ticks
    ax.set_xticks(dates)

    plt.xticks(rotation=90)
    plt.xlabel('Date')
    plt.ylabel('Emails sent')
    plt.title(title)

    if filename:
        plt.savefig(filename, bbox_inches='tight')
        return
    buffer = BytesIO()
    plt.savefig(buffer, bbox_inches='tight')
    buffer.seek(0)
    return buffer




def draw(data, title, filename=None):
    dates = []
    date_labels = []
    counts = []

    for timestamp, count in data:
        count = int(count)
        timestamp = int(timestamp / 1000)
        dt_obj = datetime.fromtimestamp(int(timestamp))
        dates.append(dt_obj)
        date_labels.append(dt_obj.strftime('%Y-%m-%d %H:%M'))
        counts.append(count)

    fig, ax = plt.subplots()
    fig.set_figwidth(32)
    fig.set_figheight(8)
    ax.plot(dates, counts, 'o-')

    format_str = mdates.DateFormatter('%Y-%m-%d %H:%M')
    ax.xaxis.set_major_formatter(format_str)

    plt.xticks(rotation=45)
    plt.xlabel('Date')
    plt.ylabel('Emails sent')
    plt.title(title)

    if filename:
        plt.savefig(filename, bbox_inches='tight')
        return
    buffer = BytesIO()
    plt.savefig(buffer, bbox_inches='tight')
    buffer.seek(0)
    return buffer
