from base64 import b64decode
from cachetools import cached, TTLCache
from datetime import datetime
import io
import pandas as pd

from bokeh.events import ValueSubmit
from bokeh.layouts import column, row
from bokeh.models import FileInput, Select, Div, TextInput
from bokeh.palettes import Category20
from bokeh.plotting import figure, curdoc

ROOT_LAYOUT = 'root'
COLUMN_SELECTOR_LAYOUT_NAME = 'column_selector'
SUMMARY_NAME = 'summary'
LOADING_NAME = 'loading'
BAR_PLOT_NAME = 'plot1'
CATEGORY_LIMIT = 19
DEFAULT_SELECTION = ''


REMOTE_DATASETS = [
    ('https://data.nextstrain.org/files/workflows/dengue/metadata_all.tsv.zst', 'dengue/all'),
    ('https://data.nextstrain.org/files/workflows/dengue/metadata_denv1.tsv.zst', 'dengue/denv1'),
    ('https://data.nextstrain.org/files/workflows/dengue/metadata_denv2.tsv.zst', 'dengue/denv2'),
    ('https://data.nextstrain.org/files/workflows/dengue/metadata_denv3.tsv.zst', 'dengue/denv3'),
    ('https://data.nextstrain.org/files/workflows/dengue/metadata_denv4.tsv.zst', 'dengue/denv4'),
    ('https://data.nextstrain.org/files/workflows/forecasts-ncov/open/nextstrain_clades/global.tsv.gz', 'forecasts-ncov/open/nextstrain_clades/global'),
    ('https://data.nextstrain.org/files/workflows/forecasts-ncov/open/nextstrain_clades/usa.tsv.gz', 'forecasts-ncov/open/nextstrain_clades/usa'),
    ('https://data.nextstrain.org/files/workflows/forecasts-ncov/open/pango_lineages/global.tsv.gz', 'forecasts-ncov/open/pango_lineages/global'),
    ('https://data.nextstrain.org/files/workflows/forecasts-ncov/open/pango_lineages/usa.tsv.gz', 'forecasts-ncov/open/pango_lineages/usa'),
    ('https://data.nextstrain.org/files/workflows/measles/metadata.tsv.zst', 'measles'),
    ('https://data.nextstrain.org/files/workflows/mpox/metadata.tsv.gz', 'mpox'),
    ('https://data.nextstrain.org/files/ncov/open/global/metadata.tsv.xz', 'ncov/open/global'),
    ('https://data.nextstrain.org/files/ncov/open/africa/metadata.tsv.xz', 'ncov/open/africa'),
    ('https://data.nextstrain.org/files/ncov/open/asia/metadata.tsv.xz', 'ncov/open/asia'),
    ('https://data.nextstrain.org/files/ncov/open/europe/metadata.tsv.xz', 'ncov/open/europe'),
    ('https://data.nextstrain.org/files/ncov/open/north-america/metadata.tsv.xz', 'ncov/open/north-america'),
    ('https://data.nextstrain.org/files/ncov/open/oceania/metadata.tsv.xz', 'ncov/open/oceania'),
    ('https://data.nextstrain.org/files/ncov/open/south-america/metadata.tsv.xz', 'ncov/open/south-america'),
    ('https://data.nextstrain.org/files/workflows/rsv/a/metadata.tsv.gz', 'rsv/a'),
    ('https://data.nextstrain.org/files/workflows/rsv/b/metadata.tsv.gz', 'rsv/b'),
    ('https://data.nextstrain.org/files/workflows/zika/metadata.tsv.zst', 'zika'),
]


# inspired by:
# https://discourse.bokeh.org/t/loading-indicator-when-data-is-being-updated/6985/6
# https://discourse.bokeh.org/t/show-loading-sign-during-calculations/4410/2
def busy(func):
    '''
    Decorator function to display loading text when the program is working on something
    '''
    def wrapper(*args, **kwargs):
        set_loading_text("Loading...")

        def work():
            # run the decorated function
            func(*args, **kwargs)
            set_loading_text("")

        curdoc().add_next_tick_callback(work)

    return wrapper


def validate_and_summarize(metadata: pd.DataFrame):
    if 'date' not in metadata.columns:
        raise Exception("Metadata must have a date column.")

    n_rows = len(metadata)
    # TODO: Use some form of numerical value so desired_num_ticks can be used to avoid abundance of date labels
    metadata['date_month'] = pd.to_datetime(metadata['date'], errors='coerce').dt.strftime("%Y-%m")
    metadata.dropna(subset=['date_month'], inplace=True)
    n_valid_rows = len(metadata)
    missing_dates_warning = ""
    if n_rows - n_valid_rows > 0:
        missing_dates_warning = f"""
            {n_rows - n_valid_rows} were dropped due to ambiguous/missing date
            information. A future version of this app may be able to extract months
            from ambiguous dates.
        """
    replace_layout(SUMMARY_NAME, Div(name=SUMMARY_NAME, text=f"""
        Metadata has {n_rows} rows. {missing_dates_warning}
    """))

    return metadata


@cached(cache=TTLCache(maxsize=1024, ttl=24*60*60))
def get_metadata(read_csv_input):
    metadata = pd.read_csv(read_csv_input, delimiter='\t')
    return validate_and_summarize(metadata)


def initial_load(read_csv_input):
    metadata = get_metadata(read_csv_input)
    plot_per_month(metadata)

    unique_value_counts = [(col, metadata[col].nunique()) for col in metadata]

    # Only include columns that have at least 3 unique values
    unique_value_counts = [(col, n) for col, n in unique_value_counts if n >= 3]
    sorted_counts = sorted(unique_value_counts, key=lambda x: x[1])

    def column_selector_callback(attr, _old_value, column):
        assert attr == 'value'
        if column == DEFAULT_SELECTION:
            return

        plot_stacked_per_month(metadata, column)

    column_selector = Select(
        name=COLUMN_SELECTOR_LAYOUT_NAME,
        title='Color By',
        options=[DEFAULT_SELECTION, *((col, f"{col} (n={count})") for col, count in sorted_counts)],
    )
    column_selector.on_change('value', column_selector_callback)
    replace_layout(COLUMN_SELECTOR_LAYOUT_NAME, column_selector)


def local_file_changed(attr, _old_value, file_contents):
    assert attr == 'value'

    set_loading_text(f"Loading local file...")

    def work():
        try:
            file = io.BytesIO(b64decode(file_contents))
            initial_load(file)
            set_loading_text("Successfully loaded.")
        except Exception as e:
            set_loading_text(f"Failed to load: {e}")

    curdoc().add_next_tick_callback(work)


def load_remote_file(url):
    set_loading_text(f"Loading {url}...")

    def work():
        try:
            initial_load(url)
            set_loading_text("Successfully loaded.")
        except Exception as e:
            set_loading_text(f"Failed to load: {e}")

    curdoc().add_next_tick_callback(work)


def dropdown_url_changed(attr, _old_value, url):
    assert attr == 'value'
    if url == DEFAULT_SELECTION:
        return

    load_remote_file(url)


def custom_url_submitted(event):
    load_remote_file(event.value)


def sort_months(months):
    # sort YYYY-MM strings - a bit hacky
    datetime_objects = [datetime.strptime(month, "%Y-%m") for month in months]
    sorted_datetime_objects = sorted(datetime_objects)
    return [dt.strftime("%Y-%m") for dt in sorted_datetime_objects]


@busy
def plot_per_month(metadata):
    months = sort_months(metadata['date_month'].unique().tolist())

    count_by_month = metadata['date_month'].value_counts(sort=False).to_dict()
    counts = [count_by_month[month] for month in months]

    p = figure(
        name=BAR_PLOT_NAME,
        sizing_mode="stretch_width",
        x_range=months,
        title="Sequences per month",
        toolbar_location="right", tools = "pan,wheel_zoom,box_zoom,reset,hover",
        tooltips="@x (n=@top)",
        )
    p.vbar(x=months, top=counts)

    p.y_range.start = 0
    p.x_range.range_padding = 0.1
    p.xgrid.grid_line_color = None
    p.xaxis.major_label_orientation = "vertical"
    p.axis.minor_tick_line_color = None
    p.outline_line_color = None

    replace_layout(BAR_PLOT_NAME, p)


@busy
def plot_stacked_per_month(metadata, column):
    months = sort_months(metadata['date_month'].unique().tolist())

    # Convert column to string to ensure categorical
    metadata[column] = metadata[column].astype(str)
    top_column_values = set(metadata[column].value_counts(sort=True, ascending=False).index[:CATEGORY_LIMIT])
    metadata['category_adj'] = metadata[column].apply(lambda v: v if v in top_column_values else 'other')
    column_values = metadata['category_adj'].unique().tolist()

    data = {
        'time': months
    }
    for category in column_values:
        data[category] = [len(metadata.query(f"{'category_adj'} == {category!r} & date_month == {month!r}")) for month in months]

    colors = Category20[len(column_values)]

    p = figure(
        name=BAR_PLOT_NAME,
        sizing_mode="stretch_width",
        x_range=months,
        title=f"Sequences per month colored by {column!r}",
        toolbar_location="right", tools = "pan,wheel_zoom,box_zoom,reset,hover",
        tooltips="$name @time (n=@$name)",
        )
    p.vbar_stack(column_values, x='time', source=data, color=colors, legend_label=column_values)

    p.y_range.start = 0
    p.x_range.range_padding = 0.1
    p.xgrid.grid_line_color = None
    p.xaxis.major_label_orientation = "vertical"
    p.axis.minor_tick_line_color = None
    p.outline_line_color = None
    p.legend.location = "top_left"
    p.legend.orientation = "horizontal"

    replace_layout(BAR_PLOT_NAME, p)


def replace_layout(name, new_layout, root_layout=None):
    if root_layout is None:
        root_layout = curdoc().get_model_by_name(ROOT_LAYOUT)

    children = root_layout.children
    old_layout = curdoc().get_model_by_name(name)
    for i, layout in enumerate(children):
        if layout == old_layout:
            children[i] = new_layout
            return
        elif hasattr(layout, 'children'):
            replace_layout(name, new_layout, root_layout=layout)


def set_loading_text(text):
    curdoc().select_one({'name': LOADING_NAME}).text = text


about_text = Div(text="""
    <h1>Nextstrain Metadata Explorer</h1>
    <a href="https://github.com/victorlin/metadata-explorer">source code</a>
""")

file_input = FileInput(title="Select a TSV file", accept=".tsv")
file_input.on_change('value', local_file_changed)

dataset_selector = Select(
    name='dataset',
    title='Load a public dataset',
    options= [DEFAULT_SELECTION, *REMOTE_DATASETS],
)
dataset_selector.on_change('value', dropdown_url_changed)

url_input = TextInput(title="URL to file")
url_input.on_event(ValueSubmit, custom_url_submitted)

column_selector = Select(
    name=COLUMN_SELECTOR_LAYOUT_NAME,
    title='Color By (select metadata first)',
    options=[],
    disabled=True,
)

summary = Div(name=SUMMARY_NAME, text="")
loading = Div(name=LOADING_NAME, text="")

p = figure(
    name=BAR_PLOT_NAME,
    sizing_mode="stretch_width",
    toolbar_location=None,
)

curdoc().add_root(column(
    about_text,
    row(file_input, Div(text="OR"), dataset_selector, Div(text="OR"), url_input),
    column_selector,
    summary,
    loading,
    p,
    name=ROOT_LAYOUT,
    sizing_mode="stretch_width",
))
