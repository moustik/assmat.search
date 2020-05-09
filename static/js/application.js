$(document).ready(function(){
    $(".custom-file-input").on("change", function() {
        var fileName = $(this).val().split("\\").pop();
        $(this).siblings(".custom-file-label").addClass("selected").html(fileName);
    });

    //connect to the socket server.
    namespace = '/test';
    var socket = io(namespace);
    var id = socket.io.engine.id
    // var socket = io.connect('http://' + document.domain + ':' + location.port);

    socket.on('connect', function() {
        // we emit a connected message to let knwo the client that we are connected.
        socket.emit('client_connected', {data: 'New client!'});
    });

    //receive message details from server
    socket.on('display_message', function(msg) {
        console.log(msg)
        message_string = '<div class="text-center"><p>' + msg.data + '</p>' +
            '<div class="spinner-border" role="status">' +
            '<span class="sr-only">Loading...</span>' +
            '</div></div>';
        $('#map').html(message_string);
    });


    $('form#upload-form').on('submit', event => {
        event.preventDefault()
        message_string = '<div class="text-center"><p>Envoi en cours ...</p>' +
            '<div class="spinner-border" style="width: 3rem; height: 3rem;" role="status">' +
            '<span class="sr-only">Loading...</span>' +
            '</div></div>';
        $('#map').html(message_string);

        let form = $('#upload-form')[0]
        var input = $("<input>").attr("type", "hidden").attr("name", "sid").val(socket.io.engine.id);
        console.log(socket.io.engine.id);
        $('#upload-form').append($(input));
        let form_data = new FormData(form)

        $.ajax({
            type: 'POST',
            url: '/view',
            data: form_data,
            contentType: false,
            cache: false,
            processData: false,
            success: function(data) {
                console.log('Success!');
                $('#map').html(data);

            },
        });

    })

});
