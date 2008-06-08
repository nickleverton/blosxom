#!/usr/bin/perl

# Blosxom
# Author: Rael Dornfest <rael@oreilly.com>
# Version: 2.0.2+njl
# Home/Docs/Licensing: http://blosxom.sourceforge.net/
# Development/Downloads: http://sourceforge.net/projects/blosxom

use warnings;
use strict;

package blosxom;

# --- Configurable variables -----

use vars
    qw! $version $blog_title $blog_description $blog_language $blog_encoding $datadir $url %template $template $put_template $depth $num_entries $file_extension $default_flavour $static_or_dynamic $config_dir $plugin_list $plugin_path $plugin_dir $plugin_state_dir @plugins %plugins $static_dir $static_password @static_flavours $static_entries $path_info_full $path_info $path_info_yr $path_info_mo $path_info_da $path_info_mo_num $flavour $static_or_dynamic %month2num @num2month $interpolate $entries $output $header $show_future_entries %files %indexes %others $encode_xml_entities !;

# What's this blog's title?
$blog_title = "My Weblog";

# What's this blog's description (for outgoing RSS feed)?
$blog_description = "Yet another Blosxom weblog.";

# What's this blog's primary language (for outgoing RSS feed)?
$blog_language = "en";

# What's this blog's text encoding ?
$blog_encoding = "UTF-8";

# Where are this blog's entries kept?
$datadir = "/Library/WebServer/Documents/blosxom";

# What's my preferred base URL for this blog (leave blank for automatic)?
$url = "";

# Should I stick only to the datadir for items or travel down the
# directory hierarchy looking for items?  If so, to what depth?
# 0 = infinite depth (aka grab everything), 1 = datadir only, n = n levels down
$depth = 0;

# How many entries should I show on the home page?
$num_entries = 40;

# What file extension signifies a blosxom entry?
$file_extension = "txt";

# What is the default flavour?
$default_flavour = "html";

# Should I show entries from the future (i.e. dated after now)?
$show_future_entries = 0;

# --- Plugins (Optional) -----

# File listing plugins blosxom should load
# (if empty blosxom will load all plugins in $plugin_dir and $plugin_path directories)
$plugin_list = "";

# Where are my plugins kept?
$plugin_dir = "";

# Where should my plugins keep their state information?
$plugin_state_dir = "$plugin_dir/state";

# Additional plugins location
# List of directories, separated by ';' on windows, ':' everywhere else
$plugin_path = "";

# --- Static Rendering -----

# Where are this blog's static files to be created?
$static_dir = "/Library/WebServer/Documents/blog";

# What's my administrative password (you must set this for static rendering)?
$static_password = "";

# What flavours should I generate statically?
@static_flavours = qw/html rss/;

# Should I statically generate individual entries?
# 0 = no, 1 = yes
$static_entries = 0;

# --- Template variables -----

# --- Callback variables -----

# --- Control variables -----

# --------------------------------

use FileHandle;
use File::Find;
use File::stat;
use Time::Local;
use CGI qw/ -compile :standard :netscape/;

$version = "2.0.2+njl";

# Should I encode entities for xml content-types? (plugins can turn this off if they do it themselves)
$encode_xml_entities = 1;

# Load configuration from $ENV{BLOSXOM_CONFIG_DIR}/blosxom.conf, if it exists
my $blosxom_config;
if ( $ENV{BLOSXOM_CONFIG_FILE} && -r $ENV{BLOSXOM_CONFIG_FILE} ) {
    $blosxom_config = $ENV{BLOSXOM_CONFIG_FILE};
    ( $config_dir = $blosxom_config ) =~ s! / [^/]* $ !!x;
}
else {
    for my $blosxom_config_dir ( $ENV{BLOSXOM_CONFIG_DIR}, '/etc/blosxom',
        '/etc' )
    {
        if ( defined( $blosxom_config_dir ) && -r "$blosxom_config_dir/blosxom.conf" ) {
            $config_dir     = $blosxom_config_dir;
            $blosxom_config = "$blosxom_config_dir/blosxom.conf";
            last;
        }
    }
}

# Load $blosxom_config
if ($blosxom_config) {
    if ( -r $blosxom_config ) {
        eval { require $blosxom_config }
            or warn "Error reading blosxom config file '$blosxom_config'"
            . ( $@ ? ": $@" : '' );
    }
    else {
        warn "Cannot find or read blosxom config file '$blosxom_config'";
    }
}

my $fh = new FileHandle;

%month2num = (
    nil => '00',
    Jan => '01',
    Feb => '02',
    Mar => '03',
    Apr => '04',
    May => '05',
    Jun => '06',
    Jul => '07',
    Aug => '08',
    Sep => '09',
    Oct => '10',
    Nov => '11',
    Dec => '12'
);
@num2month = sort { $month2num{$a} <=> $month2num{$b} } keys %month2num;

# Use the stated preferred URL or figure it out automatically
$url ||= url( -path_info => 1 );
$url =~ s/^included:/http:/ if $ENV{SERVER_PROTOCOL} eq 'INCLUDED';

# NOTE: Since v3.12, it looks as if CGI.pm misbehaves for SSIs and
# always appends path_info to the url. To fix this, we always
# request an url with path_info, and always remove it from the end of the
# string.
my $pi_len = length $ENV{PATH_INFO};
my $might_be_pi = substr( $url, -$pi_len );
substr( $url, -length $ENV{PATH_INFO} ) = ''
    if $might_be_pi eq $ENV{PATH_INFO};

$url =~ s!/$!!;

# Drop ending any / from dir settings
$datadir    =~ s!/$!!;
$plugin_dir =~ s!/$!!;
$static_dir =~ s!/$!!;

# Fix depth to take into account datadir's path
$depth += ( $datadir =~ tr[/][] ) - 1 if $depth;

# Global variable to be used in head/foot.{flavour} templates
$path_info = '';

if (    !$ENV{GATEWAY_INTERFACE}
    and param('-password')
    and $static_password
    and param('-password') eq $static_password )
{
    $static_or_dynamic = 'static';
}
else {
    $static_or_dynamic = 'dynamic';
    param( -name => '-quiet', -value => 1 );
}

# Path Info Magic
# Take a gander at HTTP's PATH_INFO for optional blog name, archive yr/mo/day
my @path_info = split m{/}, path_info() || param('path');
$path_info_full = join '/', @path_info;      # Equivalent to $ENV{PATH_INFO}
shift @path_info;

# Category/directory names denoted by leading alpha and no dot (no flavour).
while ( @path_info
    and $path_info[0] =~ /^[a-zA-Z]/
    and $path_info[0] !~ /\./ )
{
    $path_info .= '/' . shift @path_info;
}

# Flavour specified by ?flav={flav} or index.{flav}
$flavour = '';

if ( @path_info && $path_info[$#path_info] =~ /(.+)\.([^.]+)$/ ) {
    $flavour = $2;
    $path_info .= "/$1.$2" if $1 ne 'index';
    pop @path_info;
}
else {
    $flavour = param('flav') || $default_flavour;
}

# Strip leading and trailing slashes from remainder
$path_info =~ s:^/+|/+$::g;

# Date fiddling
( $path_info_yr, $path_info_mo, $path_info_da ) = @path_info;
$path_info_mo_num =
    $path_info_mo
	? ( $path_info_mo =~ /\d{2}/
	    ? $path_info_mo
	    : ( $month2num{ ucfirst( lc $path_info_mo ) } || undef ) )
	: undef;

# Define standard template subroutine, plugin-overridable at Plugins: Template
$template = sub {
    my ( $path, $chunk, $flavour ) = @_;

    do {
	# print( STDERR "templ path: $flavour, $chunk, $path" ),
        return join '', <$fh>
            if $fh->open("$datadir/$path/$chunk.$flavour", "<");
    } while ( $path && $path =~ s:/*[^/]*$:: );

    # Check for existence, avoids "if defined" instantiating hash elements that don't exist
    # whilst still returning template contents which are defined and blank.
    if ( exists $blosxom::template{$flavour}{$chunk} ) {
	# print STDERR "templ get: $flavour, $chunk, ". $blosxom::template{$flavour}{$chunk};
        return $blosxom::template{$flavour}{$chunk};
    }
    # configurable "default flavour" template - reduces configuration effort for plugin templates
    elsif ( exists $blosxom::template{default}{$chunk} ) {
	# print STDERR "templ dflt: $flavour, $chunk, ". $blosxom::template{default}{$chunk};
        return $blosxom::template{default}{$chunk};
    }
    # configurable "no such flavour" template
    elsif ( exists $blosxom::template{error}{$chunk} ) {
	# print STDERR "templ err: $flavour, $chunk, ". $blosxom::template{error}{$chunk};
        return $blosxom::template{error}{$chunk};
    }
    # no such template at all - return blank
    else {
	# print STDERR "templ null: $flavour, $chunk";
        return '';
    }
};

$put_template = sub {
    my ( $chunk, $flavour, $template ) = @_;

    $blosxom::template{$flavour}{$chunk} = $template;
    # print STDERR "templ put: $flavour, $chunk, ". $blosxom::template{$flavour}{$chunk};
};

# Bring in the templates
%template = ();
while (<DATA>) {
    last if /^(__END__)$/;
    my ( $ct, $comp, $txt ) = /^(\S+)\s(\S+)(?:\s(.*))?$/ or next;
    $txt =~ s/\\n/\n/mg;
    $template{$ct}{$comp} .= $txt . "\n";
}

# Plugins: Start
my $path_sep = $^O eq 'MSWin32' ? ';' : ':';
my @plugin_dirs = split /$path_sep/, $plugin_path;
unshift @plugin_dirs, $plugin_dir;
my @plugin_list = ();
my %plugin_hash = ();

# If $plugin_list is set, read plugins to use from that file
if ( $plugin_list ) {
    if ( -r $plugin_list and $fh->open($plugin_list, "<") ) {
        @plugin_list = map { chomp $_; $_ } grep { /\S/ && !/^#/ } <$fh>;
        $fh->close;
    }
    else {
        warn "unable to read or open plugin_list '$plugin_list': $!";
        $plugin_list = '';
    }
}

# Otherwise walk @plugin_dirs to get list of plugins to use
if ( ! @plugin_list && @plugin_dirs ) {
    for my $plugin_dir (@plugin_dirs) {
        next unless -d $plugin_dir;
        if ( opendir PLUGINS, $plugin_dir ) {
            for my $plugin (
                grep { /^[\w:]+$/ && !/~$/ && -f "$plugin_dir/$_" }
                readdir(PLUGINS) )
            {

                # Ignore duplicates
                next if $plugin_hash{$plugin};

                # Add to @plugin_list and %plugin_hash
                $plugin_hash{$plugin} = "$plugin_dir/$plugin";
                push @plugin_list, $plugin;
            }
            closedir PLUGINS;
        }
    }
    @plugin_list = sort @plugin_list;
}

# Load all plugins in @plugin_list
unshift @INC, @plugin_dirs;
foreach my $plugin (@plugin_list) {
    my ( $plugin_name, $off ) = $plugin =~ /^\d*([\w:]+?)(_?)$/;
    my $plugin_file = $plugin_list ? $plugin_name : $plugin;
    my $on_off = $off eq '_' ? -1 : 1;

    # Allow perl module plugins
    # The -z test is a hack to allow a zero-length placeholder file in a 
    #   $plugin_path directory to indicate an @INC module should be loaded
    if ( $plugin =~ m/::/ && ( $plugin_list || -z $plugin_hash{$plugin} ) ) {

     # For Blosxom::Plugin::Foo style plugins, we need to use a string require
        eval "require $plugin_file";
    }
    else
    { # we try first to load from $plugin_dir before attempting from $plugin_path
        eval        { require "$plugin_dir/$plugin_file" }
            or eval { require $plugin_file };
    }

    if ($@) {
        warn "error finding or loading blosxom plugin '$plugin_name': $@";
        next;
    }
    if ( $plugin_name->start() and ( $plugins{$plugin_name} = $on_off ) ) {
        push @plugins, $plugin_name;
    }

}
shift @INC foreach @plugin_dirs;

# Plugins: Template
# Allow for the first encountered plugin::template subroutine to override the
# default built-in template subroutine
foreach my $plugin (@plugins) {
    if ( $plugins{$plugin} > 0 and $plugin->can('template') ) {
        if ( my $tmp = $plugin->template() ) {
            $template = $tmp;
            last;
        }
    }
}

# Provide backward compatibility for Blosxom < 2.0rc1 plug-ins
sub load_template {
    return &$template(@_);
}

# Define default entries subroutine
$entries = sub {
    my ( %files, %indexes, %others );
    find(
        sub {
            my $d;
            my $curr_depth = $File::Find::dir =~ tr[/][];
            return if $depth and $curr_depth > $depth;

            if (

                # a match
                $File::Find::name
                =~ m!^$datadir/(?:(.*)/)?(.+)\.$file_extension$!

                # not an index, .file, and is readable
                and $2 ne 'index' and $2 !~ /^\./ and ( -r $File::Find::name )
                )
            {
		my( $dirname, $basename ) = ($1, $2);
		$dirname = "" unless defined $dirname;

                # read modification time
                my $mtime = stat($File::Find::name)->mtime or return;

                # to show or not to show future entries
                return unless ( $show_future_entries or $mtime < time );

                # add the file and its associated mtime to the list of files
                $files{$File::Find::name} = $mtime;

                # static rendering bits
                my $static_file
                    = "$static_dir/$dirname/index." . $static_flavours[0];
                if (   param('-all')
                    or !-f $static_file
                    or stat($static_file)->mtime < $mtime )
                {
                    $indexes{$dirname} = 1;
                    $d = join( '/', ( nice_date($mtime) )[ 5, 2, 3 ] );
                    $indexes{$d} = $d;
                    $indexes{ ( $dirname ? "$dirname/" : '' ) . "$basename.$file_extension" } = 1
                        if $static_entries;
                }
            }

            # not an entries match
            elsif ( !-d $File::Find::name and -r $File::Find::name ) {
                $others{$File::Find::name} = stat($File::Find::name)->mtime;
            }
        },
        $datadir
    );

    return ( \%files, \%indexes, \%others );
};

# Plugins: Entries
# Allow for the first encountered plugin::entries subroutine to override the
# default built-in entries subroutine
foreach my $plugin (@plugins) {
    if ( $plugins{$plugin} > 0 and $plugin->can('entries') ) {
        if ( my $tmp = $plugin->entries() ) {
            $entries = $tmp;
            last;
        }
    }
}

my ( $files, $indexes, $others ) = &$entries();
%indexes = %$indexes;

# Static
if (    !$ENV{GATEWAY_INTERFACE}
    and param('-password')
    and $static_password
    and param('-password') eq $static_password )
{

    param('-quiet') or print "Blosxom is generating static index pages...\n";

    # Home Page and Directory Indexes
    my %done;
    foreach my $path ( sort keys %indexes ) {
        my $p = '';
        foreach ( ( '', split /\//, $path ) ) {
            $p .= "/$_";
            $p =~ s!^/!!;
            next if $done{$p}++;
            mkdir "$static_dir/$p", 0755
                unless ( -d "$static_dir/$p" or $p =~ /\.$file_extension$/ );
            foreach $flavour (@static_flavours) {
                my $content_type
                    = ( &$template( $p, 'content_type', $flavour ) );
                $content_type =~ s!\n.*!!s;
                my $fn = $p =~ m!^(.+)\.$file_extension$! ? $1 : "$p/index";
                param('-quiet') or print "$fn.$flavour\n";
                my $fh_w = new FileHandle "> $static_dir/$fn.$flavour"
                    or die "Couldn't open $static_dir/$p for writing: $!";
                $output = '';
                if ( $indexes{$path} == 1 ) {

                    # category
                    $path_info = $p;

                    # individual story
                    $path_info =~ s!\.$file_extension$!\.$flavour!;
                    print $fh_w &generate( 'static', $path_info, '', $flavour,
                        $content_type );
                }
                else {

                    # date
                    local (
                        $path_info_yr, $path_info_mo,
                        $path_info_da, $path_info
                    ) = split /\//, $p, 4;
                    unless ( defined $path_info ) { $path_info = "" }
                    print $fh_w &generate( 'static', '', $p, $flavour,
                        $content_type );
                }
                $fh_w->close;
            }
        }
    }
}

# Dynamic
else {
    my $content_type = ( &$template( $path_info, 'content_type', $flavour ) );
    $content_type =~ s!\n.*!!s;

    $content_type =~ s/(\$\w+(?:::\w+)*)/"defined $1 ? $1 : ''"/gee;
    $header = { -type => $content_type };

    print generate( 'dynamic', $path_info,
        (defined($path_info_yr) ? $path_info_yr : "") ."/".
	    (defined($path_info_mo_num) ? $path_info_mo_num : "") ."/".
	    (defined($path_info_da) ? $path_info_yr : ""),
        $flavour, $content_type );
}

# Plugins: End
foreach my $plugin (@plugins) {
    if ( $plugins{$plugin} > 0 and $plugin->can('end') ) {
        $entries = $plugin->end();
    }
}

# Generate
sub generate {
    my ( $static_or_dynamic, $currentdir, $date, $flavour, $content_type )
        = @_;

    %files = %$files;
    %others = ref $others ? %$others : ();

    # Plugins: Filter
    foreach my $plugin (@plugins) {
        if ( $plugins{$plugin} > 0 and $plugin->can('filter') ) {
            $entries = $plugin->filter( \%files, \%others );
        }
    }

    my %f = %files;

    # Plugins: Skip
    # Allow plugins to decide if we can cut short story generation
    my $skip;
    foreach my $plugin (@plugins) {
        if ( $plugins{$plugin} > 0 and $plugin->can('skip') ) {
            if ( my $tmp = $plugin->skip() ) {
                $skip = $tmp;
                last;
            }
        }
    }

    # Define default interpolation subroutine
    $interpolate = sub {
        package blosxom;
        my $template = shift;
        # Interpolate scalars, namespaced scalars, and hash/hashref scalars
        $template =~ s/(\$\w+(?:::\w+)*(?:(?:->)?{(['"]?)[-\w]+\2})?)/"defined $1 ? $1 : ''"/gee;
        return $template;
    };

    unless ( defined($skip) and $skip ) {

        # Plugins: Interpolate
        # Allow for the first encountered plugin::interpolate subroutine to
        # override the default built-in interpolate subroutine
        foreach my $plugin (@plugins) {
            if ( $plugins{$plugin} > 0 and $plugin->can('interpolate') ) {
                if ( my $tmp = $plugin->interpolate() ) {
                    $interpolate = $tmp;
                    last;
                }
            }
        }

        # Head
        my $head = ( &$template( $currentdir, 'head', $flavour ) );

        # Plugins: Head
        foreach my $plugin (@plugins) {
            if ( $plugins{$plugin} > 0 and $plugin->can('head') ) {
                $entries = $plugin->head( $currentdir, \$head );
            }
        }

        $head = &$interpolate($head);

        $output .= $head;

        # Stories
        my $curdate = '';
        my $ne      = $num_entries;

        if ( $currentdir =~ /(.*?)([^\/]+)\.(.+)$/ and $2 ne 'index' ) {
            $currentdir = "$1$2.$file_extension";
            %f = ( "$datadir/$currentdir" => $files{"$datadir/$currentdir"} )
                if $files{"$datadir/$currentdir"};
        }
        else {
            $currentdir =~ s:/index\..+$::;
        }

        # Define a default sort subroutine
        my $sort = sub {
            my ($files_ref) = @_;
            return
                sort { $files_ref->{$b} <=> $files_ref->{$a} }
                keys %$files_ref;
        };

     # Plugins: Sort
     # Allow for the first encountered plugin::sort subroutine to override the
     # default built-in sort subroutine
        foreach my $plugin (@plugins) {
            if ( $plugins{$plugin} > 0 and $plugin->can('sort') ) {
                if ( my $tmp = $plugin->sort() ) {
                    $sort = $tmp;
                    last;
                }
            }
        }

        foreach my $path_file ( &$sort( \%f, \%others ) ) {
            last if $ne <= 0 && $date !~ /\d/;
            use vars qw/ $path $fn /;
            ( $path, $fn )
                = $path_file =~ m!^$datadir/(?:(.*)/)?(.*)\.$file_extension!;
	    $path = "" unless defined $path;

            # Only stories in the right hierarchy
	    next unless $path =~ /^\Q$currentdir/
                or $path_file eq "$datadir/$currentdir";

            # Prepend a slash for use in templates only if a path exists
            $path &&= "/$path";

            # Date fiddling for by-{year,month,day} archive views
            use vars
                qw/ $dw $mo $mo_num $da $ti $yr $hr $min $hr12 $ampm $utc_offset/;
            ( $dw, $mo, $mo_num, $da, $ti, $yr, $utc_offset )
                = nice_date( $files{"$path_file"} );
            ( $hr, $min ) = split /:/, $ti;
            ( $hr12, $ampm ) = $hr >= 12 ? ( $hr - 12, 'pm' ) : ( $hr, 'am' );
            if ( $hr12 == 0 ) { $hr12 = 12 }
            $hr12 =~ s/^0//;

            # Only stories from the right date
            my ( $path_info_yr, $path_info_mo_num, $path_info_da )
                = split /\//, $date;
            next if $path_info_yr     && $yr != $path_info_yr;
            last if $path_info_yr     && $yr < $path_info_yr;
            next if $path_info_mo_num && $mo ne $num2month[$path_info_mo_num];
            next if $path_info_da     && $da != $path_info_da;
            last if $path_info_da     && $da < $path_info_da;

            # Date
            my $date = ( &$template( $path, 'date', $flavour ) );

            # Plugins: Date
            foreach my $plugin (@plugins) {
                if ( $plugins{$plugin} > 0 and $plugin->can('date') ) {
                    $entries
                        = $plugin->date( $currentdir, \$date,
                        $files{$path_file}, $dw, $mo, $mo_num, $da, $ti,
                        $yr );
                }
            }

            $date = &$interpolate($date);

            if ( $date && $curdate ne $date ) {
                $curdate = $date;
                $output .= $date;
            }

            use vars qw/ $title $body $raw /;
            if ( -f "$path_file" && $fh->open($path_file, "<") ) {
                chomp( $title = <$fh> );
                chomp( $body = join '', <$fh> );
                $fh->close;
                $raw = "$title\n$body";
            }
            my $story = ( &$template( $path, 'story', $flavour ) );

            # Plugins: Story
            foreach my $plugin (@plugins) {
                if ( $plugins{$plugin} > 0 and $plugin->can('story') ) {
                    $entries = $plugin->story( $path, $fn, \$story, \$title,
                        \$body );
                }
            }

            if ( $encode_xml_entities && $content_type =~ m{\bxml\b} ) {

                # Escape <, >, and &, and to produce valid RSS
                my %escape = (
                    '<' => '&lt;',
                    '>' => '&gt;',
                    '&' => '&amp;',
                    '"' => '&quot;'
                );
                my $escape_re = join '|' => keys %escape;
                $title =~ s/($escape_re)/$escape{$1}/g;
                $body  =~ s/($escape_re)/$escape{$1}/g;
            }

            $story = &$interpolate($story);

            $output .= $story;
            $fh->close;

            $ne--;
        }

        # Foot
        my $foot = ( &$template( $currentdir, 'foot', $flavour ) );

        # Plugins: Foot
        foreach my $plugin (@plugins) {
            if ( $plugins{$plugin} > 0 and $plugin->can('foot') ) {
                $entries = $plugin->foot( $currentdir, \$foot );
            }
        }

        $foot = &$interpolate($foot);
        $output .= $foot;

        # Plugins: Last
        foreach my $plugin (@plugins) {
            if ( $plugins{$plugin} > 0 and $plugin->can('last') ) {
                $entries = $plugin->last();
            }
        }

    }    # End skip

    # Finally, add the header, if any and running dynamically
    if ( $static_or_dynamic eq 'dynamic' && $header ) {
	$header->{ '-content-length' } = length($output);
	$output = header($header) . $output;
    }

    $output;
}

sub nice_date {
    my ($unixtime) = @_;

    my $c_time = CORE::localtime($unixtime);
    my ( $dw, $mo, $da, $hr, $min, $sec, $yr )
        = ( $c_time
            =~ /(\w{3}) +(\w{3}) +(\d{1,2}) +(\d{2}):(\d{2}):(\d{2}) +(\d{4})$/
        );
    $ti = "$hr:$min";
    $da = sprintf( "%02d", $da );
    my $mo_num = $month2num{$mo};

    my $offset
        = timegm( $sec, $min, $hr, $da, $mo_num - 1, $yr - 1900 ) - $unixtime;
    my $utc_offset = sprintf( "%+03d", int( $offset / 3600 ) )
        . sprintf( "%02d", ( $offset % 3600 ) / 60 );

    return ( $dw, $mo, $mo_num, $da, $ti, $yr, $utc_offset );
}

# Default HTML and RSS template bits
__DATA__
html content_type text/html; charset=$blog_encoding

html head <html>
html head     <head>
html head         <meta http-equiv="content-type" content="text/html;charset=$blog_encoding" />
html head         <link rel="alternate" type="application/rss+xml" title="RSS" href="$url/index.rss" />
html head         <title>$blog_title $path_info_da $path_info_mo $path_info_yr
html head         </title>
html head     </head>
html head     <body>
html head         <center>
html head             <font size="+3">$blog_title</font><br />
html head             $path_info_da $path_info_mo $path_info_yr
html head         </center>
html head         <p />

html story        <p>
html story            <a name="$fn"><b>$title</b></a><br />
html story            $body<br />
html story            <br />
html story            posted at: $ti | path: <a href="$url$path">$path </a> | <a href="$url/$yr/$mo_num/$da#$fn">permanent link to this entry</a>
html story        </p>

html date         <h3>$dw, $da $mo $yr</h3>

html foot
html foot         <p />
html foot         <center>
html foot             <a href="http://blosxom.sourceforge.net/"><img src="http://blosxom.sourceforge.net/images/pb_blosxom.gif" border="0" /></a>
html foot         </center>
html foot     </body>
html foot </html>

rss content_type text/xml; charset=$blog_encoding

rss head <?xml version="1.0" encoding="$blog_encoding"?>
rss head <rss version="2.0">
rss head   <channel>
rss head     <title>$blog_title</title>
rss head     <link>$url/$path_info</link>
rss head     <description>$blog_description</description>
rss head     <language>$blog_language</language>
rss head     <docs>http://blogs.law.harvard.edu/tech/rss</docs>
rss head     <generator>blosxom/$version</generator>

rss story   <item>
rss story     <title>$title</title>
rss story     <pubDate>$dw, $da $mo $yr $ti:00 $utc_offset</pubDate>
rss story     <link>$url/$yr/$mo_num/$da#$fn</link>
rss story     <category>$path</category>
rss story     <guid isPermaLink="false">$path/$fn</guid>
rss story     <description>$body</description>
rss story   </item>

rss date 

rss foot   </channel>
rss foot </rss>

error content_type text/html

error head <html>
error head <body>
error head     <p><font color="red">Error: I'm afraid this is the first I've heard of a "$flavour" flavoured Blosxom.  Try dropping the "/+$flavour" bit from the end of the URL.</font></p>


error story <p><b>$title</b><br />
error story $body <a href="$url/$yr/$mo_num/$da#fn.$default_flavour">#</a></p>

error date <h3>$dw, $da $mo $yr</h3>

error foot     </body>
error foot </html>
__END__

