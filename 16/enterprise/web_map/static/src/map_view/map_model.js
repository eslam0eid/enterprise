/** @odoo-module **/

import { Model } from "@web/views/model";
import { session } from "@web/session";
import { browser } from "@web/core/browser/browser";
import { formatDateTime, parseDate, parseDateTime } from "@web/core/l10n/dates";
import { KeepLast } from "@web/core/utils/concurrency";

const DATE_GROUP_FORMATS = {
    year: "yyyy",
    quarter: "'Q'q yyyy",
    month: "MMMM yyyy",
    week: "'W'WW yyyy",
    day: "dd MMM yyyy",
};

export class MapModel extends Model {
    setup(params, { notification, http }) {
        this.notification = notification;
        this.http = http;

        this.metaData = {
            ...params,
            mapBoxToken: session.map_box_token || "",
        };

        this.data = {
            count: 0,
            fetchingCoordinates: false,
            groupByKey: false,
            isGrouped: false,
            numberOfLocatedRecords: 0,
            partnerIds: [],
            partners: [],
            partnerToCache: [],
            recordGroups: [],
            records: [],
            routes: [],
            routingError: null,
            shouldUpdatePosition: true,
            useMapBoxAPI: !!this.metaData.mapBoxToken,
        };

        this.coordinateFetchingTimeoutHandle = undefined;
        this.shouldFetchCoordinates = false;
        this.keepLast = new KeepLast();
    }
    /**
     * @param {any} params
     * @returns {Promise<void>}
     */
    async load(params) {
        if (this.coordinateFetchingTimeoutHandle !== undefined) {
            this.stopFetchingCoordinates();
        }
        const metaData = {
            ...this.metaData,
            ...params,
        };
        this.data = await this._fetchData(metaData);
        this.metaData = metaData;

        this.notify();
    }
    /**
     * Tells the model to stop fetching coordinates.
     * In OSM mode, the model starts to fetch coordinates once every second after the
     * model has loaded.
     * This fetching has to be done every second if we don't want to be banned from OSM.
     * There are typically two cases when we need to stop fetching:
     * - when component is about to be unmounted because the request is bound to
     *   the component and it will crash if we do so.
     * - when calling the `load` method as it will start fetching new coordinates.
     */
    stopFetchingCoordinates() {
        browser.clearTimeout(this.coordinateFetchingTimeoutHandle);
        this.coordinateFetchingTimeoutHandle = undefined;
        this.shouldFetchCoordinates = false;
    }

    //----------------------------------------------------------------------
    // Protected
    //----------------------------------------------------------------------

    /**
     * Adds the corresponding partner to a record.
     *
     * @protected
     */
    _addPartnerToRecord(metaData, data) {
        for (const record of data.records) {
            for (const partner of data.partners) {
                let recordPartnerId;
                if (metaData.resModel === "res.partner" && metaData.resPartnerField === "id") {
                    recordPartnerId = record.id;
                } else {
                    recordPartnerId = record[metaData.resPartnerField][0];
                }

                if (recordPartnerId == partner.id) {
                    record.partner = partner;
                    data.numberOfLocatedRecords++;
                }
            }
        }
    }

    /**
     * The partner's coordinates should be between -90 <= latitude <= 90 and -180 <= longitude <= 180.
     *
     * @protected
     * @param {Object} partner
     * @param {number} partner.partner_latitude latitude of the partner
     * @param {number} partner.partner_longitude longitude of the partner
     * @returns {boolean}
     */
    _checkCoordinatesValidity(partner) {
        if (
            partner.partner_latitude &&
            partner.partner_longitude &&
            partner.partner_latitude >= -90 &&
            partner.partner_latitude <= 90 &&
            partner.partner_longitude >= -180 &&
            partner.partner_longitude <= 180
        ) {
            return true;
        }
        return false;
    }

    /**
     * Handles the case of an empty map.
     * Handles the case where the model is res_partner.
     * Fetches the records according to the model given in the arch.
     * If the records has no partner_id field it is sliced from the array.
     *
     * @protected
     * @params {any} metaData
     * @return {Promise<any>}
     */
    async _fetchData(metaData) {
        const data = {
            count: 0,
            fetchingCoordinates: false,
            groupByKey: metaData.groupBy.length ? metaData.groupBy[0] : false,
            isGrouped: metaData.groupBy.length > 0,
            numberOfLocatedRecords: 0,
            partnerIds: [],
            partners: [],
            partnerToCache: [],
            recordGroups: [],
            records: [],
            routes: [],
            routingError: null,
            shouldUpdatePosition: true,
            useMapBoxAPI: !!metaData.mapBoxToken,
        };

        //case of empty map
        if (!metaData.resPartnerField) {
            data.recordGroups = [];
            data.records = [];
            data.routes = [];
            return this.keepLast.add(Promise.resolve(data));
        }
        const results = await this.keepLast.add(this._fetchRecordData(metaData, data));
        
        const datetimeFields=metaData.fieldNames.filter(name=>metaData.fields[name].type=="datetime");
        for(let record of results.records){
            // convert date fields from UTC to local timezone
            for(const field of datetimeFields){
                if (record[field]) {
                    const dateUTC = luxon.DateTime.fromFormat(
                        record[field],
                        "yyyy-MM-dd HH:mm:ss",
                        { zone: "UTC" }
                    );
                    record[field] = formatDateTime(dateUTC, { format: "yyyy-MM-dd HH:mm:ss" });
                }
            }
        }

        data.records = results.records;
        data.count = results.length;
        if (data.isGrouped) {
            data.recordGroups = await this._getRecordGroups(metaData, data);
        } else {
            data.recordGroups = [];
        }

        data.partnerIds = [];
        if (metaData.resModel === "res.partner" && metaData.resPartnerField === "id") {
            for (const record of data.records) {
                data.partnerIds.push(record.id);
                record.partner_id = [record.id];
            }
        } else {
            this._fillPartnerIds(metaData, data);
        }

        data.partnerIds = [...new Set(data.partnerIds)];
        await this._partnerFetching(metaData, data);

        return data;
    }

    /**
     * Fetch the records for a given model.
     *
     * @protected
     * @returns {Promise}
     */
    _fetchRecordData(metaData, data) {
        const fields = data.groupByKey
            ? metaData.fieldNames.concat(data.groupByKey.split(":")[0])
            : metaData.fieldNames;
        const orderBy = [];
        if (metaData.defaultOrder) {
            orderBy.push(metaData.defaultOrder.name);
            if (metaData.defaultOrder.asc) {
                orderBy.push("ASC");
            }
        }
        return this.orm.webSearchRead(metaData.resModel, metaData.domain, fields, {
            limit: metaData.limit,
            offset: metaData.offset,
            order: orderBy.join(" "),
            context: metaData.context,
        });
    }

    /**
     * This function convert the addresses to coordinates using the mapbox API.
     *
     * @protected
     * @param {Object} record this object contains the record fetched from the database.
     * @returns {Promise} result.query contains the query the the api received
     *      result.features contains results in descendant order of relevance
     */
    _fetchCoordinatesFromAddressMB(metaData, data, record) {
        const address = encodeURIComponent(record.contact_address_complete);
        const token = metaData.mapBoxToken;
        const encodedUrl = `https://api.mapbox.com/geocoding/v5/mapbox.places/${address}.json?access_token=${token}&cachebuster=1552314159970&autocomplete=true`;
        return this.http.get(encodedUrl);
    }

    /**
     * This function convert the addresses to coordinates using the openStreetMap api.
     *
     * @protected
     * @param {Object} record this object contains the record fetched from the database.
     * @returns {Promise} result is an array that contains the result in descendant order of relevance
     *      result[i].lat is the latitude of the converted address
     *      result[i].lon is the longitude of the converted address
     *      result[i].importance is a number that the relevance of the result the closer the number is to one the best it is.
     */
    _fetchCoordinatesFromAddressOSM(metaData, data, record) {
        const address = encodeURIComponent(record.contact_address_complete.replace("/", " "));
        const encodedUrl = `https://nominatim.openstreetmap.org/search?q=${address}&format=jsonv2`;
        return this.http.get(encodedUrl);
    }

    /**
     * @protected
     * @param {number[]} ids contains the ids from the partners
     * @returns {Promise}
     */
    _fetchRecordsPartner(metaData, data, ids) {
        const domain = [
            ["contact_address_complete", "!=", "False"],
            ["id", "in", ids],
        ];
        const fields = ["contact_address_complete", "partner_latitude", "partner_longitude"];
        return this.orm.searchRead("res.partner", domain, fields);
    }

    /**
     * Fetch the route from the mapbox api.
     *
     * @protected
     * @returns {Promise}
     *      results.geometry.legs[i] contains one leg (i.e: the trip between two markers).
     *      results.geometry.legs[i].steps contains the sets of coordinates to follow to reach a point from an other.
     *      results.geometry.legs[i].distance: the distance in meters to reach the destination
     *      results.geometry.legs[i].duration the duration of the leg
     *      results.geometry.coordinates contains the sets of coordinates to go from the first to the last marker without the notion of waypoint
     */
    _fetchRoute(metaData, data) {
        const coordinatesParam = data.records
            .filter((record) => record.partner && record.partner.partner_latitude && record.partner.partner_longitude)
            .map(({ partner }) => `${partner.partner_longitude},${partner.partner_latitude}`);
        const address = encodeURIComponent(coordinatesParam.join(";"));
        const token = metaData.mapBoxToken;
        const encodedUrl = `https://api.mapbox.com/directions/v5/mapbox/driving/${address}?access_token=${token}&steps=true&geometries=geojson`;
        return this.http.get(encodedUrl);
    }

    /**
     * @protected
     * @param {Object[]} records the records that are going to be filtered
     */
    _fillPartnerIds(metaData, data) {
        for (const record of data.records) {
            if (record[metaData.resPartnerField]) {
                data.partnerIds.push(record[metaData.resPartnerField][0]);
            }
        }
    }

    /**
     * Converts a MapBox error message into a custom translatable one.
     *
     * @protected
     * @param {string} message
     */
    _getErrorMessage(message) {
        const ERROR_MESSAGES = {
            "Too many coordinates; maximum number of coordinates is 25": this.env._t(
                "Too many routing points (maximum 25)"
            ),
            "Route exceeds maximum distance limitation": this.env._t(
                "Some routing points are too far apart"
            ),
            "Too Many Requests": this.env._t("Too many requests, try again in a few minutes"),
        };
        return ERROR_MESSAGES[message];
    }

    /**
     * @protected
     * @returns {Object} the fetched records grouped by the groupBy field.
     */
    async _getRecordGroups(metaData, data) {
        const [fieldName, subGroup] = data.groupByKey.split(":");
        const groups = {};
        const idToFetch = {};
        const fieldType = metaData.fields[fieldName].type;
        for (const record of data.records) {
            const value = record[fieldName];
            let id, name;
            if (["date", "datetime"].includes(fieldType) && value) {
                const date = fieldType === "date" ? parseDate(value) : parseDateTime(value);
                id = name = date.toFormat(DATE_GROUP_FORMATS[subGroup]);
            } else if (fieldType === "boolean") {
                id = name = value ? this.env._t("Yes") : this.env._t("No");
            } else {
                id = Array.isArray(value) ? value[0] : value;
                name = Array.isArray(value) ? value[1] : value;
            }

            if (id === false && name === false) {
                id = name = this.env._t("None");
            }

            if (["many2many", "one2many"].includes(fieldType) && value.length) {
                for (const m2mId of value) {
                    idToFetch[m2mId] = undefined;
                }
            } else if (!groups[id]) {
                groups[id] = {
                    name,
                    records: [],
                };
            }
            if (!["many2many", "one2many"].includes(fieldType) || !value.length) {
                groups[id].records.push(record);
            }
        }
        if (["many2many", "one2many"].includes(fieldType)) {
            const m2mList = await this.orm.nameGet(
                metaData.fields[fieldName].relation,
                Object.keys(idToFetch).map(Number)
            );
            for (const [m2mId, m2mName] of m2mList) {
                idToFetch[m2mId] = m2mName;
            }

            for (const record of data.records) {
                for (const m2mId of record[fieldName]) {
                    if (!groups[m2mId]) {
                        groups[m2mId] = {
                            name: idToFetch[m2mId],
                            records: [],
                        };
                    }
                    groups[m2mId].records.push(record);
                }
            }
        }
        return groups;
    }

    /**
     * Handles the case where the selected api is MapBox.
     * Iterates on all the partners and fetches their coordinates when they're not set.
     *
     * @protected
     * @return {Promise} if there's more than 2 located records and the routing option is activated it returns a promise that fetches the route
     *      resultResult is an object that contains the computed route
     *      or if either of these conditions are not respected it returns an empty promise
     */
    _maxBoxAPI(metaData, data) {
        const promises = [];
        for (const partner of data.partners) {
            if (
                partner.contact_address_complete &&
                (!partner.partner_latitude || !partner.partner_longitude)
            ) {
                promises.push(
                    this._fetchCoordinatesFromAddressMB(metaData, data, partner).then(
                        (coordinates) => {
                            if (coordinates.features.length) {
                                partner.partner_longitude =
                                    parseFloat(coordinates.features[0].geometry.coordinates[0]);
                                partner.partner_latitude =
                                    parseFloat(coordinates.features[0].geometry.coordinates[1]);
                                data.partnerToCache.push(partner);
                            }
                        }
                    )
                );
            } else if (!this._checkCoordinatesValidity(partner)) {
                partner.partner_latitude = undefined;
                partner.partner_longitude = undefined;
            }
        }
        return Promise.all(promises).then(() => {
            data.routes = [];
            if (data.numberOfLocatedRecords > 1 && metaData.routing && !data.groupByKey) {
                return this._fetchRoute(metaData, data).then((routeResult) => {
                    if (routeResult.routes) {
                        data.routes = routeResult.routes;
                    } else {
                        data.routingError = this._getErrorMessage(routeResult.message);
                    }
                });
            } else {
                return Promise.resolve();
            }
        });
    }

    /**
     * Handles the displaying of error message according to the error.
     *
     * @protected
     * @param {Object} err contains the error returned by the requests
     * @param {number} err.status contains the status_code of the failed http request
     */
    _mapBoxErrorHandling(metaData, data, err) {
        switch (err.status) {
            case 401:
                this.notification.add(
                    this.env._t(
                        "The view has switched to another provider but functionalities will be limited"
                    ),
                    {
                        title: this.env._t("Token invalid"),
                        type: "danger",
                    }
                );
                break;
            case 403:
                this.notification.add(
                    this.env._t(
                        "The view has switched to another provider but functionalities will be limited"
                    ),
                    {
                        title: this.env._t("Unauthorized connection"),
                        type: "danger",
                    }
                );
                break;
            case 422: // Max. addresses reached
            case 429: // Max. requests reached
                data.routingError = this._getErrorMessage(err.responseJSON.message);
                break;
            case 500:
                this.notification.add(
                    this.env._t(
                        "The view has switched to another provider but functionalities will be limited"
                    ),
                    {
                        title: this.env._t("MapBox servers unreachable"),
                        type: "danger",
                    }
                );
        }
    }

    /**
     * Notifies the fetched coordinates to server and controller.
     *
     * @protected
     */
    _notifyFetchedCoordinate(metaData, data) {
        this._writeCoordinatesUsers(metaData, data);
        data.shouldUpdatePosition = false;
        this.notify();
    }

    /**
     * Calls (without awaiting) _openStreetMapAPIAsync with a delay of 1000ms
     * to not get banned from openstreetmap's server.
     *
     * Tests should patch this function to wait for coords to be fetched.
     *
     * @see _openStreetMapAPIAsync
     * @protected
     * @return {Promise}
     */
    _openStreetMapAPI(metaData, data) {
        this._openStreetMapAPIAsync(metaData, data);
        return Promise.resolve();
    }
    /**
     * Handles the case where the selected api is open street map.
     * Iterates on all the partners and fetches their coordinates when they're not set.
     *
     * @protected
     * @returns {Promise}
     */
    _openStreetMapAPIAsync(metaData, data) {
        // Group partners by address to reduce address list
        const addressPartnerMap = new Map();
        for (const partner of data.partners) {
            if (
                partner.contact_address_complete &&
                (!partner.partner_latitude || !partner.partner_longitude)
            ) {
                if (!addressPartnerMap.has(partner.contact_address_complete)) {
                    addressPartnerMap.set(partner.contact_address_complete, []);
                }
                addressPartnerMap.get(partner.contact_address_complete).push(partner);
                partner.fetchingCoordinate = true;
            } else if (!this._checkCoordinatesValidity(partner)) {
                partner.partner_latitude = undefined;
                partner.partner_longitude = undefined;
            }
        }

        // `fetchingCoordinates` is used to display the "fetching banner"
        // We need to check if there are coordinates to fetch before reload the
        // view to prevent flickering
        data.fetchingCoordinates = addressPartnerMap.size > 0;
        this.shouldFetchCoordinates = true;
        const fetch = async () => {
            const partnersList = Array.from(addressPartnerMap.values());
            for (let i = 0; i < partnersList.length; i++) {
                await new Promise((resolve) => {
                    this.coordinateFetchingTimeoutHandle = browser.setTimeout(
                        resolve,
                        this.constructor.COORDINATE_FETCH_DELAY
                    );
                });
                if (!this.shouldFetchCoordinates) {
                    return;
                }
                const partners = partnersList[i];
                try {
                    const coordinates = await this._fetchCoordinatesFromAddressOSM(
                        metaData,
                        data,
                        partners[0]
                    );
                    if (!this.shouldFetchCoordinates) {
                        return;
                    }
                    if (coordinates.length) {
                        for (const partner of partners) {
                            partner.partner_longitude = parseFloat(coordinates[0].lon);
                            partner.partner_latitude = parseFloat(coordinates[0].lat);
                            data.partnerToCache.push(partner);
                        }
                    }
                    for (const partner of partners) {
                        partner.fetchingCoordinate = false;
                    }
                    data.fetchingCoordinates = i < partnersList.length - 1;
                    this._notifyFetchedCoordinate(metaData, data);
                } catch (_e) {
                    for (const partner of data.partners) {
                        partner.fetchingCoordinate = false;
                    }
                    data.fetchingCoordinates = false;
                    this.shouldFetchCoordinates = false;
                    this.notification.add(
                        this.env._t("OpenStreetMap's request limit exceeded, try again later."),
                        { type: "danger" }
                    );
                    this.notify();
                }
            }
        };
        return fetch();
    }

    /**
     * Fetches the partner which ids are contained in the the array partnerids
     * if the token is set it uses the mapBoxApi to fetch address and route
     * if not is uses the openstreetmap api to fetch the address.
     *
     * @protected
     * @param {number[]} partnerIds this array contains the ids from the partner that are linked to records
     * @returns {Promise}
     */
    async _partnerFetching(metaData, data) {
        data.partners = data.partnerIds.length
            ? await this.keepLast.add(this._fetchRecordsPartner(metaData, data, data.partnerIds))
            : [];
        this._addPartnerToRecord(metaData, data);
        if (data.useMapBoxAPI) {
            return this.keepLast
                .add(this._maxBoxAPI(metaData, data))
                .then(() => {
                    this._writeCoordinatesUsers(metaData, data);
                })
                .catch((err) => {
                    this._mapBoxErrorHandling(metaData, data, err);
                    data.useMapBoxAPI = false;
                    return this._openStreetMapAPI(metaData, data);
                });
        } else {
            return this._openStreetMapAPI(metaData, data).then(() => {
                this._writeCoordinatesUsers(metaData, data);
            });
        }
    }
    /**
     * Writes partner_longitude and partner_latitude of the res.partner model.
     *
     * @protected
     * @return {Promise}
     */
    async _writeCoordinatesUsers(metaData, data) {
        const partners = data.partnerToCache;
        data.partnerToCache = [];
        if (partners.length) {
            await this.orm.call("res.partner", "update_latitude_longitude", [partners], {
                context: metaData.context,
            });
        }
    }
}

MapModel.services = ["notification", "http"];
MapModel.COORDINATE_FETCH_DELAY = 1000;
