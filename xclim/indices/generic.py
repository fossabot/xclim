# -*- coding: utf-8 -*-
# noqa: D205,D400
"""
Generic indices submodule
=========================

Helper functions for common generic actions done in the computation of indices.
"""
from typing import Optional, Sequence, Tuple, Union

import cftime
import numpy as np
import xarray
import xarray as xr
from xarray.coding.cftime_offsets import _MONTH_ABBREVIATIONS, to_cftime_datetime

from xclim.core.calendar import (
    convert_calendar,
    days_in_year,
    doy_to_days_since,
    get_calendar,
    uniform_calendars,
)
from xclim.core.units import (
    convert_units_to,
    declare_units,
    pint2cfunits,
    str2pint,
    to_agg_units,
)

from ..core.utils import DayOfYearStr
from . import run_length as rl

__all__ = [
    "aggregate_between_dates",
    "compare",
    "count_level_crossings",
    "count_occurrences",
    "day_lengths",
    "default_freq",
    "degree_days",
    "diurnal_temperature_range",
    "domain_count",
    "doymax",
    "doymin",
    "get_daily_events",
    "get_op",
    "interday_diurnal_temperature_range",
    "last_occurrence",
    "select_resample_op",
    "select_time",
    "statistics",
    "temperature_sum",
    "threshold_count",
    "thresholded_statistics",
]

binary_ops = {">": "gt", "<": "lt", ">=": "ge", "<=": "le", "==": "eq", "!=": "ne"}


def select_time(
    da: Union[xr.DataArray, xr.Dataset],
    drop: bool = False,
    season: Union[str, Sequence[str]] = None,
    month: Union[int, Sequence[int]] = None,
    doy_bounds: Tuple[int, int] = None,
    date_bounds: Tuple[str, str] = None,
):
    """Select entries according to a time period.

    This conveniently improves xarray's :py:meth:`xarray.DataArray.where` and
    :py:meth:`xarray.DataArray.sel` with fancier ways of indexing over time elements.
    In addition to the data `da` and argument `drop`, only one of `season`, `month`,
    `doy_bounds` or `date_bounds` may be passed.

    Parameters
    ----------
    da : xr.DataArray or xr.Dataset
      Input data.
    drop: boolean
      Whether to drop elements outside the period of interest or
      to simply mask them (default).
    season: string or sequence of strings
      One or more of 'DJF', 'MAM', 'JJA' and 'SON'.
    month: integer or sequence of integers
      Sequence of month numbers (January = 1 ... December = 12)
    doy_bounds: 2-tuple of integers
      The bounds as (start, end) of the period of interest expressed in day-of-year,
      integers going from 1 (January 1st) to 365 or 366 (December 31st). If calendar
      awareness is needed, consider using ``date_bounds`` instead.
      Bounds are inclusive.
    date_bounds: 2-tuple of strings
      The bounds as (start, end) of the period of interest expressed as dates in the
      month-day (%m-%d) format.
      Bounds are inclusive.

    Returns
    -------
    xr.DataArray or xr.Dataset
      Selected input values. If ``drop=False``, this has the same length as ``da``
      (along dimension 'time'), but with masked (NaN) values outside the period of
      interest.

    Examples
    --------
    Keep only the values of fall and spring.

    >>> ds = open_dataset("ERA5/daily_surface_cancities_1990-1993.nc")
    >>> ds.time.size
    1461
    >>> out = select_time(ds, drop=True, season=['MAM', 'SON'])
    >>> out.time.size
    732

    Or all values between two dates (included).

    >>> out = select_time(ds, drop=True, date_bounds=('02-29', '03-02'))
    >>> out.time.values
    array(['1990-03-01T00:00:00.000000000', '1990-03-02T00:00:00.000000000',
           '1991-03-01T00:00:00.000000000', '1991-03-02T00:00:00.000000000',
           '1992-02-29T00:00:00.000000000', '1992-03-01T00:00:00.000000000',
           '1992-03-02T00:00:00.000000000', '1993-03-01T00:00:00.000000000',
           '1993-03-02T00:00:00.000000000'], dtype='datetime64[ns]')
    """
    N = sum(arg is not None for arg in [season, month, doy_bounds, date_bounds])
    if N > 1:
        raise ValueError(f"Only one method of indexing may be given, got {N}.")

    if N == 0:
        return da

    def get_doys(start, end):
        if start <= end:
            return np.arange(start, end + 1)
        return np.concatenate((np.arange(start, 367), np.arange(0, end + 1)))

    if season is not None:
        if isinstance(season, str):
            season = [season]
        mask = da.time.dt.season.isin(season)

    elif month is not None:
        if isinstance(month, int):
            month = [month]
        mask = da.time.dt.month.isin(month)

    elif doy_bounds is not None:
        mask = da.time.dt.dayofyear.isin(get_doys(*doy_bounds))

    elif date_bounds is not None:
        # This one is a bit trickier.
        start, end = date_bounds
        time = da.time
        calendar = get_calendar(time)
        if calendar not in uniform_calendars:
            # For non-uniform calendars, we can't simply convert dates to doys
            # conversion to all_leap is safe for all non-uniform calendar as it doesn't remove any date.
            time = convert_calendar(time, "all_leap")
            # values of time are the _old_ calendar
            # and the new calendar is in the coordinate
            calendar = "all_leap"

        # Get doy of date, this is now safe because the calendar is uniform.
        doys = get_doys(
            to_cftime_datetime("2000-" + start, calendar).dayofyr,
            to_cftime_datetime("2000-" + end, calendar).dayofyr,
        )
        mask = time.time.dt.dayofyear.isin(doys)
        # Needed if we converted calendar, this puts back the correct coord
        mask["time"] = da.time

    return da.where(mask, drop=drop)


def select_resample_op(da: xr.DataArray, op: str, freq: str = "YS", **indexer):
    """Apply operation over each period that is part of the index selection.

    Parameters
    ----------
    da : xr.DataArray
      Input data.
    op : str {'min', 'max', 'mean', 'std', 'var', 'count', 'sum', 'argmax', 'argmin'} or func
      Reduce operation. Can either be a DataArray method or a function that can be applied to a DataArray.
    freq : str
      Resampling frequency defining the periods as defined in
      https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#resampling.
    indexer : {dim: indexer, }, optional
      Time attribute and values over which to subset the array. For example, use season='DJF' to select winter values,
      month=1 to select January, or month=[6,7,8] to select summer months. If not indexer is given, all values are
      considered.

    Returns
    -------
    xarray.DataArray
      The maximum value for each period.
    """
    da = select_time(da, **indexer)
    r = da.resample(time=freq)
    if isinstance(op, str):
        return getattr(r, op)(dim="time", keep_attrs=True)

    return r.map(op)


def doymax(da: xr.DataArray) -> xr.DataArray:
    """Return the day of year of the maximum value."""
    i = da.argmax(dim="time")
    out = da.time.dt.dayofyear.isel(time=i, drop=True)
    out.attrs.update(units="", is_dayofyear=1, calendar=get_calendar(da))
    return out


def doymin(da: xr.DataArray) -> xr.DataArray:
    """Return the day of year of the minimum value."""
    i = da.argmin(dim="time")
    out = da.time.dt.dayofyear.isel(time=i, drop=True)
    out.attrs.update(units="", is_dayofyear=1, calendar=get_calendar(da))
    return out


def default_freq(**indexer) -> str:
    """Return the default frequency."""
    freq = "AS-JAN"
    if indexer:
        group, value = indexer.popitem()
        if group == "season":
            month = 12  # The "season" scheme is based on AS-DEC
        elif group == "month":
            month = np.take(value, 0)
        elif group == "doy_bounds":
            month = cftime.num2date(value[0] - 1, "days since 2004-01-01").month
        elif group == "date_bounds":
            month = int(value[0][:2])
        freq = "AS-" + _MONTH_ABBREVIATIONS[month]
    return freq


def get_op(op: str):
    """Get python's comparing function according to its name of representation.

    Accepted op string are keys and values of xclim.indices.generic.binary_ops.
    """
    if op in binary_ops:
        op = binary_ops[op]
    elif op in binary_ops.values():
        pass
    else:
        raise ValueError(f"Operation `{op}` not recognized.")
    return xr.core.ops.get_op(op)  # noqa


def compare(da: xr.DataArray, op: str, thresh: Union[float, int]) -> xr.DataArray:
    """Compare a dataArray to a threshold using given operator.

    Parameters
    ----------
    da : xr.DataArray
      Input data.
    op : {">", "<", ">=", "<=", "gt", "lt", "ge", "le"}
      Logical operator {>, <, >=, <=, gt, lt, ge, le }. e.g. arr > thresh.
    thresh : Union[float, int]
      Threshold value.

    Returns
    -------
    xr.DataArray
        Boolean mask of the comparison.
    """
    return get_op(op)(da, thresh)


def threshold_count(
    da: xr.DataArray, op: str, thresh: Union[float, int, xr.DataArray], freq: str
) -> xr.DataArray:
    """Count number of days where value is above or below threshold.

    Parameters
    ----------
    da : xr.DataArray
      Input data.
    op : {">", "<", ">=", "<=", "gt", "lt", "ge", "le"}
      Logical operator {>, <, >=, <=, gt, lt, ge, le }. e.g. arr > thresh.
    thresh : Union[float, int]
      Threshold value.
    freq : str
      Resampling frequency defining the periods as defined in
      https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#resampling.

    Returns
    -------
    xr.DataArray
      The number of days meeting the constraints for each period.
    """
    c = compare(da, op, thresh) * 1
    return c.resample(time=freq).sum(dim="time")


def domain_count(da: xr.DataArray, low: float, high: float, freq: str) -> xr.DataArray:
    """Count number of days where value is within low and high thresholds.

    A value is counted if it is larger than `low`, and smaller or equal to `high`, i.e. in `]low, high]`.

    Parameters
    ----------
    da : xr.DataArray
      Input data.
    low : float
      Minimum threshold value.
    high : float
      Maximum threshold value.
    freq : str
      Resampling frequency defining the periods defined in
      https://pandas.pydata.org/pandas-docs/stable/user_guide/timeseries.html#resampling.

    Returns
    -------
    xr.DataArray
      The number of days where value is within [low, high] for each period.
    """
    c = compare(da, ">", low) * compare(da, "<=", high) * 1
    return c.resample(time=freq).sum(dim="time")


def get_daily_events(da: xr.DataArray, da_value: float, operator: str) -> xr.DataArray:
    r"""Return a 0/1 mask when a condition is True or False.

    the function returns 1 where operator(da, da_value) is True
                         0 where operator(da, da_value) is False
                         nan where da is nan

    Parameters
    ----------
    da : xr.DataArray
    da_value : float
    operator : {">", "<", ">=", "<=", "gt", "lt", "ge", "le"}
      Logical operator {>, <, >=, <=, gt, lt, ge, le}. e.g. arr > thresh.

    Returns
    -------
    xr.DataArray
    """
    func = getattr(da, "_binary_op")(get_op(operator))
    events = func(da, da_value) * 1
    events = events.where(~(np.isnan(da)))
    events = events.rename("events")
    return events


# CF-INDEX-META Indices


def count_level_crossings(
    low_data: xr.DataArray, high_data: xr.DataArray, threshold: str, freq: str
) -> xr.DataArray:
    """Calculate the number of times low_data is below threshold while high_data is above threshold.

    First, the threshold is transformed to the same standard_name and units as the input data,
    then the thresholding is performed, and finally, the number of occurrences is counted.

    Parameters
    ----------
    low_data: xr.DataArray
      Variable that must be under the threshold.
    high_data: xr.DataArray
      Variable that must be above the threshold.
    threshold: str
      Quantity.
    freq: str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray
    """
    # Convert units to low_data
    high_data = convert_units_to(high_data, low_data)
    threshold = convert_units_to(threshold, low_data)

    lower = compare(low_data, "<", threshold)
    higher = compare(high_data, ">=", threshold)

    out = (lower & higher).resample(time=freq).sum()
    return to_agg_units(out, low_data, "count", dim="time")


def count_occurrences(
    data: xr.DataArray, threshold: str, condition: str, freq: str
) -> xr.DataArray:
    """Calculate the number of times some condition is met.

    First, the threshold is transformed to the same standard_name and units as the input data.
    Then the thresholding is performed as condition(data, threshold),
    i.e. if condition is `<`, then this counts the number of times `data < threshold`.
    Finally, count the number of occurrences when condition is met.

    Parameters
    ----------
    data : xr.DataArray
    threshold : str
      Quantity.
    condition : {">", "<", ">=", "<=", "==", "!="}
      Operator.
    freq: str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray
    """
    threshold = convert_units_to(threshold, data)

    cond = compare(data, condition, threshold)

    out = cond.resample(time=freq).sum()
    return to_agg_units(out, data, "count", dim="time")


def diurnal_temperature_range(
    low_data: xr.DataArray, high_data: xr.DataArray, reducer: str, freq: str
) -> xr.DataArray:
    """Calculate the diurnal temperature range and reduce according to a statistic.

    Parameters
    ----------
    low_data : xr.DataArray
      Lowest daily temperature (tasmin).
    high_data : xr.DataArray
      Highest daily temperature (tasmax).
    reducer : {'max', 'min', 'mean', 'sum'}
      Reducer.
    freq: str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray
    """
    high_data = convert_units_to(high_data, low_data)

    dtr = high_data - low_data
    out = getattr(dtr.resample(time=freq), reducer)()

    u = str2pint(low_data.units)
    out.attrs["units"] = pint2cfunits(u - u)
    return out


def first_occurrence(
    data: xr.DataArray, threshold: str, condition: str, freq: str
) -> xr.DataArray:
    """Calculate the first time some condition is met.

    First, the threshold is transformed to the same standard_name and units as the input data.
    Then the thresholding is performed as condition(data, threshold), i.e. if condition is <, data < threshold.
    Finally, locate the first occurrence when condition is met.

    Parameters
    ----------
    data : xr.DataArray
    threshold : str
      Quantity
    condition : {">", "<", ">=", "<=", "==", "!="}
      Operator
    freq : str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray
    """
    threshold = convert_units_to(threshold, data)

    cond = compare(data, condition, threshold)

    out = cond.resample(time=freq).map(
        rl.first_run,
        window=1,
        dim="time",
        coord="dayofyear",
    )
    out.attrs["units"] = ""
    return out


def last_occurrence(
    data: xr.DataArray, threshold: str, condition: str, freq: str
) -> xr.DataArray:
    """Calculate the last time some condition is met.

    First, the threshold is transformed to the same standard_name and units as the input data.
    Then the thresholding is performed as condition(data, threshold), i.e. if condition is <, data < threshold.
    Finally, locate the last occurrence when condition is met.

    Parameters
    ----------
    data : xr.DataArray
    threshold : str
      Quantity
    condition : {">", "<", ">=", "<=", "==", "!="}
      Operator
    freq : str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray
    """
    threshold = convert_units_to(threshold, data)

    cond = compare(data, condition, threshold)

    out = cond.resample(time=freq).map(
        rl.last_run,
        window=1,
        dim="time",
        coord="dayofyear",
    )
    out.attrs["units"] = ""
    return out


def spell_length(
    data: xr.DataArray, threshold: str, condition: str, reducer: str, freq: str
) -> xr.DataArray:
    """Calculate statistics on lengths of spells.

    First, the threshold is transformed to the same standard_name and units as the input data.
    Then the thresholding is performed as condition(data, threshold), i.e. if condition is <, data < threshold.
    Then the spells are determined, and finally the statistics according to the specified reducer are calculated.

    Parameters
    ----------
    data : xr.DataArray
    threshold : str
      Quantity.
    condition : {">", "<", ">=", "<=", "==", "!="}
      Operator
    reducer : {'max', 'min', 'mean', 'sum'}
      Reducer.
    freq : str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray
    """
    threshold = convert_units_to(threshold, data)

    cond = compare(data, condition, threshold)

    out = cond.resample(time=freq).map(
        rl.rle_statistics,
        reducer=reducer,
        dim="time",
    )
    return to_agg_units(out, data, "count")


def statistics(data: xr.DataArray, reducer: str, freq: str) -> xr.DataArray:
    """Calculate a simple statistic of the data.

    Parameters
    ----------
    data : xr.DataArray
    reducer : {'max', 'min', 'mean', 'sum'}
      Reducer.
    freq : str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray
    """
    out = getattr(data.resample(time=freq), reducer)()
    out.attrs["units"] = data.attrs["units"]
    return out


def thresholded_statistics(
    data: xr.DataArray, threshold: str, condition: str, reducer: str, freq: str
) -> xr.DataArray:
    """Calculate a simple statistic of the data for which some condition is met.

    First, the threshold is transformed to the same standard_name and units as the input data.
    Then the thresholding is performed as condition(data, threshold), i.e. if condition is <, data < threshold.
    Finally, the statistic is calculated for those data values that fulfill the condition.

    Parameters
    ----------
    data : xr.DataArray
    threshold : str
      Quantity.
    condition : {">", "<", ">=", "<=", "==", "!="}
      Operator
    reducer : {'max', 'min', 'mean', 'sum'}
      Reducer.
    freq : str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray
    """
    threshold = convert_units_to(threshold, data)

    cond = compare(data, condition, threshold)

    out = getattr(data.where(cond).resample(time=freq), reducer)()
    out.attrs["units"] = data.attrs["units"]
    return out


def temperature_sum(
    data: xr.DataArray, threshold: str, condition: str, freq: str
) -> xr.DataArray:
    """Calculate the temperature sum above/below a threshold.

    First, the threshold is transformed to the same standard_name and units as the input data.
    Then the thresholding is performed as condition(data, threshold), i.e. if condition is <, data < threshold.
    Finally, the sum is calculated for those data values that fulfill the condition after subtraction of the threshold value.
    If the sum is for values below the threshold the result is multiplied by -1.

    Parameters
    ----------
    data : xr.DataArray
    threshold : str
      Quantity
    condition : {">", "<", ">=", "<=", "==", "!="}
      Operator
    freq : str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray
    """
    threshold = convert_units_to(threshold, data)

    cond = compare(data, condition, threshold)
    direction = -1 if "<" in condition else 1

    out = (data - threshold).where(cond).resample(time=freq).sum()
    out = direction * out
    return to_agg_units(out, data, "delta_prod")


def interday_diurnal_temperature_range(
    low_data: xr.DataArray, high_data: xr.DataArray, freq: str
) -> xr.DataArray:
    """Calculate the average absolute day-to-day difference in diurnal temperature range.

    Parameters
    ----------
    low_data : xr.DataArray
      Lowest daily temperature (tasmin).
    high_data : xr.DataArray
      Highest daily temperature (tasmax).
    freq: str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray
    """
    high_data = convert_units_to(high_data, low_data)

    vdtr = abs((high_data - low_data).diff(dim="time"))
    out = vdtr.resample(time=freq).mean(dim="time")

    u = str2pint(low_data.units)
    out.attrs["units"] = pint2cfunits(u - u)
    return out


def extreme_temperature_range(
    low_data: xr.DataArray, high_data: xr.DataArray, freq: str
) -> xr.DataArray:
    """Calculate the extreme temperature range as the maximum of daily maximum temperature minus the minimum of daily minimum temperature.

    Parameters
    ----------
    low_data : xr.DataArray
      Lowest daily temperature (tasmin).
    high_data : xr.DataArray
      Highest daily temperature (tasmax).
    freq: str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray
    """
    high_data = convert_units_to(high_data, low_data)

    out = (high_data - low_data).resample(time=freq).mean()

    u = str2pint(low_data.units)
    out.attrs["units"] = pint2cfunits(u - u)
    return out


def aggregate_between_dates(
    data: xr.DataArray,
    start: Union[xr.DataArray, DayOfYearStr],
    end: Union[xr.DataArray, DayOfYearStr],
    op: str = "sum",
    freq: Optional[str] = None,
):
    """Aggregate the data over a period between start and end dates and apply the operator on the aggregated data.

    Parameters
    ----------
    data : xr.DataArray
      Data to aggregate between start and end dates.
    start : xr.DataArray or DayOfYearStr
      Start dates (as day-of-year) for the aggregation periods.
    end : xr.DataArray or DayOfYearStr
      End (as day-of-year) dates for the aggregation periods.
    op : {'min', 'max', 'sum', 'mean', 'std'}
      Operator.
    freq : str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray, [dimensionless]
      Aggregated data between the start and end dates. If the end date is before the start date, returns np.nan.
      If there is no start and/or end date, returns np.nan.
    """

    def _get_days(_bound, _group, _base_time):
        """Get bound in number of days since base_time. Bound can be a days_since array or a DayOfYearStr."""
        if isinstance(_bound, str):
            b_i = rl.index_of_date(_group.time, _bound, max_idxs=1)  # noqa
            if not len(b_i):
                return None
            return (_group.time.isel(time=b_i[0]) - _group.time.isel(time=0)).dt.days
        if _base_time in _bound.time:
            return _bound.sel(time=_base_time)
        return None

    if freq is None:
        frequencies = []
        for i, bound in enumerate([start, end], start=1):
            try:
                frequencies.append(xr.infer_freq(bound.time))
            except AttributeError:
                frequencies.append(None)

        good_freq = set(frequencies) - {None}

        if len(good_freq) != 1:
            raise ValueError(
                f"Non-inferrable resampling frequency or inconsistent frequencies. Got start, end = {frequencies}."
                " Please consider providing `freq` manually."
            )
        freq = good_freq.pop()

    cal = get_calendar(data, dim="time")

    if not isinstance(start, str):
        start = convert_calendar(start, cal)
        start.attrs["calendar"] = cal
        start = doy_to_days_since(start)
    if not isinstance(end, str):
        end = convert_calendar(end, cal)
        end.attrs["calendar"] = cal
        end = doy_to_days_since(end)

    out = list()
    for base_time, indexes in data.resample(time=freq).groups.items():
        # get group slice
        group = data.isel(time=indexes)

        start_d = _get_days(start, group, base_time)
        end_d = _get_days(end, group, base_time)

        # convert bounds for this group
        if start_d is not None and end_d is not None:

            days = (group.time - base_time).dt.days
            days[days < 0] = np.nan

            masked = group.where((days >= start_d) & (days <= end_d - 1))
            res = getattr(masked, op)(dim="time", skipna=True)
            res = xr.where(
                ((start_d > end_d) | (start_d.isnull()) | (end_d.isnull())), np.nan, res
            )
            # Re-add the time dimension with the period's base time.
            res = res.expand_dims(time=[base_time])
            out.append(res)
        else:
            # Get an array with the good shape, put nans and add the new time.
            res = (group.isel(time=0) * np.nan).expand_dims(time=[base_time])
            out.append(res)
            continue

    out = xr.concat(out, dim="time")
    return out


@declare_units(tas="[temperature]")
def degree_days(tas: xr.DataArray, thresh: str, condition: str) -> xr.DataArray:
    """Calculate the degree days below/above the temperature threshold.

    Parameters
    ----------
    tas : xr.DataArray
      Mean daily temperature.
    thresh : str
      The temperature threshold.
    condition : {"<", ">"}
      Operator.

    Returns
    -------
    xarray.DataArray
    """
    thresh = convert_units_to(thresh, tas)

    if "<" in condition:
        out = (thresh - tas).clip(0)
    elif ">" in condition:
        out = (tas - thresh).clip(0)
    else:
        raise NotImplementedError(f"Condition not supported: '{condition}'.")

    out = to_agg_units(out, tas, op="delta_prod")
    return out


def day_lengths(
    dates: xr.DataArray,
    lat: xr.DataArray,
    obliquity: float = -0.4091,
    summer_solstice: DayOfYearStr = "06-21",
    start_date: Optional[Union[xarray.DataArray, DayOfYearStr]] = None,
    end_date: Optional[Union[xarray.DataArray, DayOfYearStr]] = None,
    freq: str = "YS",
) -> xr.DataArray:
    r"""Day-lengths according to latitude, obliquity, and day of year.

    Parameters
    ----------
    dates: xr.DataArray
    lat: xarray.DataArray
      Latitude coordinate.
    obliquity: float
      Obliquity of the elliptic (radians). Default: -0.4091.
    summer_solstice: DayOfYearStr
      Date of summer solstice in northern hemisphere. Used for approximating solar julian dates.
    start_date: xarray.DataArray or DayOfYearStr, optional
    end_date: xarray.DataArray or DayOfYearStr, optional
    freq : str
      Resampling frequency.

    Returns
    -------
    xarray.DataArray
      If start and end date provided, returns total sum of daylight-hour between dates at provided frequency.
      If no start and end date provided, returns day-length in hours per individual day.

    Notes
    -----
    Daylight-hours are dependent on latitude, :math:`lat`, the Julian day (solar day) from the summer solstice in the
    Northern hemisphere, :math:`Jday`, and the axial tilt :math:`Axis`, therefore day-length at any latitude for a given
    date on Earth, :math:`dayLength_{lat_{Jday}}`, for a given year in days, :math:`Year`, can be approximated as
    follows:

    .. math::
        dayLength_{lat_{Jday}} = f({lat}, {Jday}) = \frac{\arccos(1-m_{lat_{Jday}})}{\pi} * 24

    Where:

    .. math::
        m_{lat_{Jday}} = f({lat}, {Jday}) = 1 - \tan({Lat}) * \tan \left({Axis}*\cos\left[\frac{2*\pi*{Jday}}{||{Year}||} \right] \right)

    The total sum of daylight hours for a given period between two days (:math:`{Jday} = 0` -> :math:`N`) within a solar
    year then is:

    .. math::
        \sum({SeasonDayLength_{lat}}) = \sum_{Jday=1}^{N} dayLength_{lat_{Jday}}

    References
    ----------
    Modified day-length equations for Huglin heliothermal index published in Hall, A., & Jones, G. V. (2010). Spatial
    analysis of climate in winegrape-growing regions in Australia. Australian Journal of Grape and Wine Research, 16(3),
    389‑404. https://doi.org/10.1111/j.1755-0238.2010.00100.x

    Examples available from Glarner, 2006 (http://www.gandraxa.com/length_of_day.xml).
    """
    cal = get_calendar(dates)

    year_length = dates.time.copy(
        data=[days_in_year(x, calendar=cal) for x in dates.time.dt.year]
    )

    julian_date_from_solstice = dates.time.copy(
        data=doy_to_days_since(
            dates.time.dt.dayofyear, start=summer_solstice, calendar=cal
        )
    )

    m_lat_dayofyear = 1 - np.tan(np.radians(lat)) * np.tan(
        obliquity * (np.cos((2 * np.pi * julian_date_from_solstice) / year_length))
    )

    day_length_hours = (np.arccos(1 - m_lat_dayofyear) / np.pi) * 24

    if start_date and end_date:
        return aggregate_between_dates(
            day_length_hours, start=start_date, end=end_date, op="sum", freq=freq
        )
    else:
        return day_length_hours
