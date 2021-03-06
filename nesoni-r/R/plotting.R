
aspect.ratio <- function() { par()$fin[1] / par()$fin[2] }

put.plot <- function(px1,px2,py1,py2) {
    width <- par()$fin[1]
    height <- par()$fin[2]
    
    par(
        mai=c(0,0,0,0),
        plt=c(px1,px2,py1,py2),
        new=TRUE
    )
}

color.legend <- function(col, breaks, title='') {
    basic.image(x=breaks,y=c(0),z=matrix(breaks,ncol=1), col=col,breaks=breaks)
    axis(1, las=2)
    mtext(title)
}


dendrogram.paths <- function(dend) {   
   if (is.leaf(dend)) {
       ''
   } else {
       result <- c()
       for(i in 1:length(dend)) {
           result <- c(result, paste(sprintf('%d',length(dend)-i), dendrogram.paths(dend[[i]])))
       }
       result
   }
}

do.dendrogram <- function(mat, enable=TRUE) {
    if (nrow(mat) < 3 || !enable) {
        list(
            dendrogram = NA,
            order = basic.seq(nrow(mat)),
            paths = rep('',nrow(mat))
        )
    } else {
        dist.mat <- dist(mat)
        control <- list(hclust = hclust(dist.mat))
        dend.mat <- as.dendrogram(
                seriation::seriate(dist.mat, 
                method = 'OLO', control = control)[[1]])
        
        list(dendrogram = dend.mat, 
             order = order.dendrogram(dend.mat),
             paths = dendrogram.paths(dend.mat)
        )
    }
}

trim.labels <- function(labels) {
    labels <- as.character(labels)
    n <- max(10, ceiling( mean(nchar(labels)) * 3.0 ))
    
    for(i in basic.seq(length(labels)))
        if (nchar(labels[i]) > n) {
            m <- n
            for(j in 1:n)
                if (any(substr(labels[i],j,j) == c(' ',',',';')))
                   m <- j
            labels[i] <- sprintf("%s...",substr(labels[i],1,m))
        }
    
    labels
}



nesoni.heatmap <- function(mat, labels, reorder.columns=FALSE) {    
    n.rows <- nrow(mat)
    n.cols <- ncol(mat)
    
    dend.row <- do.dendrogram( t(scale(t(mat))) )
    dend.col <- do.dendrogram( scale(t(mat)), enable=reorder.columns )
    
    if (n.rows < 2 || n.cols < 2) {
        plot.new()
        title(sprintf('Can\'t plot %d x %d heatmap', n.rows, n.cols))
    } else {
        dend.row.x1 <- 1/90
        dend.row.x2 <- 1/9
        
        dend.col.y1 <- 1.0 - dend.row.x2 * aspect.ratio()
        dend.col.y2 <- 1.0 - (1.0-dend.col.y1)*0.1
        
        y1 <- 4 / par()$fin[2]
        y2 <- dend.col.y1
        
        x1 <- dend.row.x2
        x2 <- 1/3

        legend.y2 <- y1*0.75
        legend.y1 <- legend.y2 - 0.03*aspect.ratio()
        legend.x1 <- 15/30
        legend.x2 <- 18/30

        col <- signed.col
        extreme <- max(0.0,abs(mat),na.rm=TRUE)
        breaks <- seq(-extreme,extreme, length=length(col)+1)
        
        plot.new()
        
        if (!all(is.na(dend.col$dendrogram))) {
            put.plot(x1,x2, dend.col.y1,dend.col.y2)
            plot(dend.col$dendrogram, horiz=FALSE, axes=FALSE, yaxs="i", leaflab="none")
        }
        
        if (!all(is.na(dend.row$dendrogram))) {
            put.plot(dend.row.x1,dend.row.x2, y1,y2)
            plot(dend.row$dendrogram, horiz=TRUE, axes=FALSE, yaxs="i", leaflab="none")
        }
        
        put.plot(x1,x2, y1,y2)
        basic.image(1:n.cols,1:n.rows, t(mat[dend.row$order,dend.col$order,drop=FALSE]), col=col, breaks=breaks)
        axis(1, at=1:n.cols, labels=colnames(mat), las=2, tick=FALSE)

        line <- 0
        for(i in basic.seq(length(labels))) {
            if (i < length(labels))
                l <- trim.labels(labels[[i]])
            else
                l <- as.character(labels[[i]])
            axis(4, at=1:n.rows, labels=l[dend.row$order], las=2, tick=FALSE, line=line)
            line <- line + 0.45 * max(0,nchar(l))
        }
        
        put.plot(legend.x1,legend.x2, legend.y1,legend.y2)
        color.legend(col, breaks, 'log2 expression\ndifference from row average\n')        
    }
    
    list(
        dend.row = dend.row,
        dend.col = dend.col
    )   
}

#nesoni.heatmap <- function(x, reorder.columns=FALSE,dist.row=NA,dist.col=NA, ...) {    
    #if(!is.matrix(x)) x <- as.matrix(x)
    #
    #if (all(is.na(dist.row))) 
    #    dist.row <- dist( t(scale(t(x))) )
    #
    #if (all(is.na(dist.col)) && reorder.columns) 
    #    dist.col <- dist( scale(t(x)) )
    #
    #method <- 'OLO'
    #
    #if (reorder.columns) {   
    #    control <- list(hclust = hclust(dist.col))
    #    dend.col <- as.dendrogram(
    #            seriation::seriate(dist.col, 
    #            method = method, control = control)[[1]])
    #    dend <- 'both'
    #} else {    
    #    dend.col <- NA
    #    dend <- 'row'
    #}
    #
    #control <- list(hclust = hclust(dist.row))
    #dend.row <- as.dendrogram(
    #        seriation::seriate(dist.row, 
    #        method = method, control = control)[[1]])
    #
    #result <- gplots::heatmap.2(x, Colv = dend.col, Rowv = dend.row, dendrogram = dend, 
    #                  scale = "none", trace='none', density.info='none', 
    #                  lwid=c(2,par("din")[1]-2), lhei=c(1.5,par("din")[2]-1.5),
    #                  cexCol=1.0,
    #                  ...)
    #
    #invisible(result)
#}    

unsigned.col <- hsv(h=seq(0.95,1.15, length.out=256)%%1.0, v=seq(0,1, length.out=256)**0.5,s=seq(1,0,length.out=256)**0.5)
signed.col <- hsv(h=(sign(seq(-1.0,1.0, length.out=256))*0.2+0.8)%%1.0, v=1,s=abs(seq(-1,1,length.out=256)))

hmap.elist <- function(filename.prefix, elist, 
                       min.sd=0.0, min.span=0.0, min.svd=0.0, svd.rank=NULL,
                       annotation=c('gene', 'product'), 
                       res=150, row.labels=NA,
                       reorder.columns = FALSE) {
    keep <- rep(TRUE, nrow(elist$E))

    if (min.sd > 0.0) {
        sd <- sqrt(row.apply(elist$E, var))
        keep <- (keep & sd >= min.sd)
    }
    
    if (min.span > 0.0) {    
        span <- row.apply(elist$E, max) - row.apply(elist$E, min)
        keep <- (keep & span >= min.span)
    }
    
    if (min.svd > 0.0) {
        if (is.null(svd.rank))
            svd.rank <- ncol(elist$E)-1
        s <- svd(t(scale(t(elist$E), center=TRUE,scale=FALSE)), nu=svd.rank,nv=svd.rank)
        cat('SVD d diagonal:\n')
        print(s$d[basic.seq(svd.rank)])
        mag <- sqrt( rowSums(s$u*s$u) * nrow(s$u) / ncol(s$u) )
        keep <- (keep & mag >= min.svd)
    }
    
    elist <- elist[keep,]
    
    if (is.na(row.labels))
        row.labels <- (nrow(elist) <= 300)

    data <- t(scale(t(elist$E), center=TRUE,scale=FALSE))

    labels <- list(rownames(data))
    
    for(colname in annotation)
        if (!all(is.na(elist$gene[,colname])))
            labels[[ length(labels)+1 ]] <- elist$gene[,colname]
        
    height <- if(row.labels) (25*nrow(data)+800)*res/150 else 2500*res/150    
    png(sprintf('%s.png',filename.prefix), width=2000*res/150, height=height, res=res)
    
    #heatmap <- nesoni.heatmap(data, col=signed.col, symkey=TRUE,symbreaks=TRUE, labRow=(if(row.labels) NULL else NA), margins=margins, main=main, ...)
    heatmap <- nesoni.heatmap(data, labels=if(row.labels) labels else list(), reorder.columns=reorder.columns)

    dev.off()

    shuffled.elist <- elist[rev(heatmap$dend.row$order),]
    
    table.filename <- sprintf('%s.csv', filename.prefix)
    
    sink(table.filename)
    cat('# Heatmap data\n')
    cat('#\n')
    cat('# Values given are log2 reads per million\n')
    cat('#\n')
    cat(sprintf('# %d genes shown\n', nrow(data)))
    cat('#\n')

    frame <- data.frame(name=rownames(shuffled.elist$E), row.names=rownames(shuffled.elist$E), check.names=FALSE) 
    for(colname in annotation) {
        frame[,colname] <- shuffled.elist$gene[,colname]
    }     
    #frame[,'cluster hierarchy'] <- rev(dendrogram.paths(heatmap$rowDendrogram))
    frame[,'cluster hierarchy'] <- rev(heatmap$dend.row$paths)
    frame <- data.frame(frame, shuffled.elist$E, check.names=FALSE)
    
    write.csv(frame, row.names=FALSE)
    sink()

    invisible(list(heatmap=heatmap, frame=frame))
}

